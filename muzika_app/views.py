# muzika_app/views.py

from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required # <-- Supervartotojui/personalui
from django.views.decorators.http import require_POST
from django.contrib.auth import login, get_user_model, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.utils import timezone
from django.http import HttpResponseForbidden, JsonResponse
from django.db import IntegrityError, transaction, models
from django.db.models import Sum, Count, Q, F
from django.core.exceptions import ValidationError
import re
from collections import defaultdict

from .models import Group, generate_unique_code, Membership, Game, Song, Vote
from .forms import (
    GroupForm, SignUpForm, GameForm, SongForm,
    UserProfileEditForm
)

User = get_user_model()


# Pagalbinė funkcija lietuviškai galūnei (Statistikai)
def get_lithuanian_score_ending(score):
    if score is None: return ""
    try: score = int(score)
    except (ValueError, TypeError): return ""
    if score % 100 >= 11 and score % 100 <= 19: return "taškų"
    elif score % 10 == 1: return "taškas"
    elif score % 10 >= 2 and score % 10 <= 9: return "taškai"
    else: return "taškų"


@login_required
def redirect_to_primary_group_or_my_groups(request):
    """ Nukreipia į paskutinę lankytą arba pirmą pagal abėcėlę grupę / 'Mano grupes'. """
    target_group_code = None
    target_group_found = False

    last_visited_code = request.session.get('last_visited_group_code')
    if last_visited_code:
        if Membership.objects.filter(user=request.user, group__code=last_visited_code).exists():
            target_group_code = last_visited_code
            target_group_found = True
        else:
            if 'last_visited_group_code' in request.session:
                 del request.session['last_visited_group_code']

    if not target_group_found:
        first_membership = Membership.objects.filter(user=request.user).select_related('group').order_by('group__name').first()
        if first_membership:
            target_group_code = first_membership.group.code
            target_group_found = True

    if target_group_found:
        return redirect(reverse('group_admin', kwargs={'group_code': target_group_code}))
    else:
        return redirect(reverse('my_groups'))


def landing_or_home_view(request):
    """ Pagrindinis vaizdas: nukreipia prisijungusius, rodo pasitikimą neprisijungusiems. """
    if request.user.is_authenticated:
        return redirect_to_primary_group_or_my_groups(request)
    else:
        return render(request, 'muzika_app/landing.html')


@login_required
def create_group_page(request):
    """ Paruošia ir rodo grupės kūrimo puslapį. """
    unique_code = generate_unique_code()
    form = GroupForm()
    context = {'form': form, 'code': unique_code}
    return render(request, 'muzika_app/create_group.html', context)


@login_required
@require_POST
def save_group(request):
    """ Išsaugo naujai sukurtą grupę. """
    if request.method == 'POST':
        form = GroupForm(request.POST)
        code = request.POST.get('code')
        if Group.objects.filter(code=code).exists():
            messages.error(request, 'Įvyko klaida generuojant unikalų kodą. Bandykite kurti grupę iš naujo.')
            return redirect('create_group_page')
        if form.is_valid():
            group = form.save(commit=False)
            group.code = code
            group.creator = request.user
            group.save()
            Membership.objects.create(group=group, user=request.user, role=Membership.Role.ADMIN)
            messages.success(request, f'Grupė "{group.name}" (kodas: {group.code}) sėkmingai sukurta!')
            return redirect('group_admin', group_code=group.code)
        else:
            messages.error(request, 'Formoje yra klaidų. Prašome pataisyti.')
            context = {'form': form, 'code': code}
            return render(request, 'muzika_app/create_group.html', context)
    else:
        return redirect('create_group_page')


@login_required
def group_admin_view(request, group_code):
    """ Rodo grupės administravimo puslapį. """
    group = get_object_or_404(Group, code=group_code)

    is_member = Membership.objects.filter(group=group, user=request.user).exists()
    is_allowed_to_view = is_member or request.user.is_superuser
    if not is_allowed_to_view:
         messages.error(request, "Neturite teisės peržiūrėti šios grupės.")
         return redirect('my_groups')

    if is_member: # Sesiją atnaujinam tik tikram nariui
        request.session['last_visited_group_code'] = group.code

    memberships = group.membership_set.select_related('user').all()
    is_current_user_admin = request.user.is_superuser or memberships.filter(user=request.user, role=Membership.Role.ADMIN).exists()
    admin_count = memberships.filter(role=Membership.Role.ADMIN).count()

    now = timezone.now()
    active_game = None
    active_phase = None
    all_voted = False

    active_games_qs = group.games.filter(
        models.Q(submission_start_date__lte=now, submission_end_date__gte=now) |
        models.Q(voting_start_date__lte=now, voting_end_date__gte=now)    ).order_by('-created_at')

    for game in active_games_qs:
        if game.is_voting_active():
            active_game = game
            active_phase = 'voting'
            if active_game:
                group_member_ids = set(memberships.values_list('user_id', flat=True))
                voter_ids = set(Vote.objects.filter(game=active_game).values_list('voter_id', flat=True).distinct())
                if group_member_ids == voter_ids and len(group_member_ids) > 0:
                    all_voted = True
            break
        elif game.is_submission_active():
            active_game = game
            active_phase = 'submission'
            break

    last_completed_game = None
    winners = []
    if not active_game:
        latest_finished_game = Game.objects.filter(
            group=group, voting_end_date__isnull=False, voting_end_date__lte=now
        ).order_by('-voting_end_date').prefetch_related('winners').first() # Pridėtas prefetch

        if latest_finished_game:
            last_completed_game = latest_finished_game
            winners = list(latest_finished_game.winners.all()) # Gaunam laimėtojus iš M2M

    # --- Dainos kėlimo/redagavimo modalui (tik kėlimo fazėje) ---
    user_song = None
    song_form = None
    if active_game and active_phase == 'submission' and is_member:
        user_song = Song.objects.filter(game=active_game, submitted_by=request.user).first()
        song_form = SongForm(instance=user_song) if user_song else SongForm()

    context = {
        'group': group,
        'memberships': memberships,
        'is_current_user_admin': is_current_user_admin,
        'admin_count': admin_count,
        'active_game': active_game,
        'active_phase': active_phase,
        'all_voted': all_voted,
        'last_completed_game': last_completed_game,
        'winners': winners,
        'user_song': user_song,
        'song_form': song_form,
    }
    return render(request, 'muzika_app/group_admin.html', context)


@login_required
@require_POST
def change_member_role(request, group_code, member_id):
    """ Keičia nario rolę. Leidžiama adminui arba supervartotojui. """
    group = get_object_or_404(Group, code=group_code)
    is_allowed = request.user.is_superuser or Membership.objects.filter(group=group, user=request.user, role=Membership.Role.ADMIN).exists()
    if not is_allowed:
        messages.error(request, 'Neturite teisės keisti narių rolių šioje grupėje.')
        return redirect('group_admin', group_code=group.code)

    membership_to_change = get_object_or_404(Membership, group=group, user__id=member_id)
    new_role = request.POST.get('role')
    valid_roles = [role[0] for role in Membership.Role.choices]
    if new_role not in valid_roles:
        messages.error(request, 'Nurodyta negalima rolė.')
        return redirect('group_admin', group_code=group.code)

    admin_count = Membership.objects.filter(group=group, role=Membership.Role.ADMIN).count()
    if membership_to_change.role == Membership.Role.ADMIN and admin_count <= 1 and new_role == Membership.Role.MEMBER:
         # Leidžiam keisti tik jei tai NE PASKUTINIS adminas ARBA veiksmą atlieka supervartotojas
         if membership_to_change.user != request.user and not request.user.is_superuser:
              messages.error(request, 'Negalima pašalinti paskutinio administratoriaus rolės.')
              return redirect('group_admin', group_code=group.code)

    membership_to_change.role = new_role
    membership_to_change.save()
    messages.success(request, f"Nario {membership_to_change.user.username} rolė sėkmingai pakeista į '{membership_to_change.get_role_display()}'.")
    return redirect('group_admin', group_code=group.code)


def signup_view(request):
    """ Tvarko vartotojo registraciją. """
    if request.method == 'POST':
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'Sveikiname prisiregistravus, {user.username}!')
            return redirect('home')
        else:
             messages.error(request, 'Registracijos formoje yra klaidų. Prašome pataisyti.')
    else:
        form = SignUpForm()
    context = {'form': form}
    return render(request, 'registration/signup.html', context)


@login_required
def my_groups_view(request):
    """ Rodo vartotojo grupių sąrašą. """
    user_memberships = Membership.objects.filter(user=request.user).select_related('group').order_by('group__name')
    context = {'memberships': user_memberships}
    return render(request, 'muzika_app/my_groups.html', context)


@login_required
def my_songs_view(request):
    """ Rodo prisijungusio vartotojo įkeltų dainų istoriją su taškais ir vietomis. """
    now = timezone.now()

    songs = (
        Song.objects
        .filter(submitted_by=request.user)
        .select_related('game', 'game__group')
        .annotate(total_points=Sum('votes__points'))
        .order_by('-submitted_at')
    )

    songs_data = []
    total_points_sum = 0
    wins_count = 0

    for song in songs:
        game = song.game
        points = song.total_points or 0
        total_points_sum += points

        # Nustatome etapą
        if game.is_voting_finished():
            status = 'ended'
        elif game.voting_start_date and game.voting_start_date <= now:
            status = 'voting'
        else:
            status = 'submission'

        # Apskaičiuojame vietą (rank) tik kai balsavimas baigtas
        rank = None
        if status == 'ended':
            ranked = list(
                Song.objects.filter(game=game)
                .annotate(tp=Sum('votes__points'))
                .order_by('-tp')
                .values_list('id', 'tp')
            )
            place = 0
            last_points = None
            for idx, (sid, tp) in enumerate(ranked, start=1):
                if tp != last_points:
                    place = idx
                    last_points = tp
                if sid == song.id:
                    rank = place
                    break

        is_winner = game.winners.filter(id=request.user.id).exists() and rank == 1

        if is_winner:
            wins_count += 1

        songs_data.append({
            'song': song,
            'game': game,
            'group': game.group,
            'points': points,
            'status': status,
            'rank': rank,
            'is_winner': is_winner,
        })

    total_songs = len(songs_data)
    avg_points = round(total_points_sum / total_songs, 1) if total_songs else 0

    context = {
        'songs_data': songs_data,
        'total_songs': total_songs,
        'total_points': total_points_sum,
        'avg_points': avg_points,
        'wins_count': wins_count,
    }
    return render(request, 'muzika_app/my_songs.html', context)



# --- ŽAIDIMŲ VALDYMAS ---

@login_required
def create_game_view(request, group_code):
    """ Kuria naują žaidimą. """
    group = get_object_or_404(Group, code=group_code)
    now = timezone.now()

    # <<< PRADŽIA: Patikrinimas ar grupei leidžiama kurti žaidimus >>>
    # Supervartotojas gali kurti visada
    if not (group.can_create_games or request.user.is_superuser):
        messages.error(request, f"Grupėje '{group.name}' šiuo metu neleidžiama kurti naujų žaidimų.")
        return redirect('group_admin', group_code=group.code)
    # <<< PABAIGA >>>


    # --- Teisių patikrinimas (kas gali kurti: admin, laimėtojas, superuser) ---
    can_create_game = False
    # ... (likusi teisių tikrinimo logika (is_admin, last_completed_game ir t.t.) lieka tokia pati) ...
    is_admin = Membership.objects.filter(group=group, user=request.user, role=Membership.Role.ADMIN).exists()
    if request.user.is_superuser or is_admin:
        can_create_game = True
    else:
        last_completed_game = Game.objects.filter(
            group=group, voting_end_date__isnull=False, voting_end_date__lte=now, winners__isnull=False
        ).order_by('-voting_end_date').prefetch_related('winners').first()
        if last_completed_game and last_completed_game.winners.filter(id=request.user.id).exists():
            can_create_game = True

    # Jei praėjo bendrą grupės patikrinimą, bet neturi individualios teisės
    if not can_create_game:
        messages.error(request, "Neturite teisės kurti žaidimų šioje grupėje (nesate adminas ar paskutinis laimėtojas).")
        return redirect('group_admin', group_code=group.code)
    # --- Teisių patikrinimo pabaiga ---

    if request.method == 'POST':
        form = GameForm(request.POST)
        if form.is_valid():
            game = form.save(commit=False)
            game.group = group
            game.creator = request.user
            game.save()
            messages.success(request, f'Žaidimas "{game.name}" sėkmingai sukurtas!')
            return redirect('group_games_list', group_code=group.code)
        else:
            messages.error(request, 'Formoje yra klaidų. Prašome pataisyti.')
    else:
        form = GameForm()
    context = {'form': form, 'group': group}
    return render(request, 'muzika_app/create_game.html', context)


@login_required
def edit_game_view(request, group_code, game_id):
    """ Redaguoja žaidimo nustatymus. Leidžiama adminui arba supervartotojui. """
    group = get_object_or_404(Group, code=group_code)
    game = get_object_or_404(Game, id=game_id, group=group)

    is_allowed = request.user.is_superuser or Membership.objects.filter(group=group, user=request.user, role=Membership.Role.ADMIN).exists()
    if not is_allowed:
        messages.error(request, "Tik grupės administratoriai (arba supervartotojas) gali redaguoti žaidimus.")
        return redirect('group_games_list', group_code=group.code)

    if request.method == 'POST':
        form = GameForm(request.POST, instance=game)
        if form.is_valid():
            form.save()
            messages.success(request, f'Žaidimo "{game.name}" informacija sėkmingai atnaujinta!')
            return redirect('group_games_list', group_code=group.code) # Pakeista iš group_admin
        else:
            messages.error(request, 'Formoje yra klaidų. Prašome pataisyti.')
    else:
        form = GameForm(instance=game)

    context = {'form': form, 'group': group, 'game': game}
    return render(request, 'muzika_app/edit_game.html', context)


@login_required
@require_POST
def delete_game_view(request, group_code, game_id):
    """ Trina žaidimą. Leidžiama adminui arba supervartotojui. """
    group = get_object_or_404(Group, code=group_code)
    game = get_object_or_404(Game, id=game_id, group=group)

    is_allowed = request.user.is_superuser or Membership.objects.filter(group=group, user=request.user, role=Membership.Role.ADMIN).exists()
    if not is_allowed:
        messages.error(request, "Tik grupės administratoriai (arba supervartotojas) gali trinti žaidimus.")
        return redirect('group_games_list', group_code=group.code)

    try:
        game_name = game.name
        game.delete()
        messages.success(request, f'Žaidimas "{game_name}" sėkmingai ištrintas.')
    except Exception as e:
        messages.error(request, f"Įvyko klaida trinant žaidimą: {e}")
    return redirect('group_games_list', group_code=group.code)


@login_required
def group_games_list_view(request, group_code):
    """ Rodo grupės žaidimų sąrašą. Leidžiama nariui arba supervartotojui. """
    group = get_object_or_404(Group, code=group_code)

    is_member = Membership.objects.filter(group=group, user=request.user).exists()
    is_allowed = is_member or request.user.is_superuser
    if not is_allowed:
         messages.error(request, "Neturite teisės peržiūrėti šios grupės žaidimų.")
         return redirect('my_groups')

    games_qs = Game.objects.filter(group=group).select_related('creator').order_by('-created_at')
    is_current_user_admin = request.user.is_superuser or (is_member and Membership.objects.filter(group=group, user=request.user, role=Membership.Role.ADMIN).exists())

    user_songs_map = {
        song.game_id: song.id        for song in Song.objects.filter(game__in=games_qs, submitted_by=request.user).only('id', 'game_id')
    }

    games_list = []
    for game in games_qs:
        game.user_song_id = user_songs_map.get(game.id, None)
        games_list.append(game)

    # Ar šiai grupei / vartotojui leidžiama kurti žaidimus (modalui)
    can_create_game = (group.can_create_games or request.user.is_superuser) and is_current_user_admin

    context = {
        'group': group,
        'games': games_list,
        'is_current_user_admin': is_current_user_admin,
        'game_form': GameForm() if can_create_game else None,
        'can_create_game': can_create_game,
    }
    return render(request, 'muzika_app/group_games_list.html', context)


@login_required
def game_details_view(request, group_code, game_id):
    """ Rodo žaidimo detales. Leidžiama nariui arba supervartotojui. """
    group = get_object_or_404(Group, code=group_code)
    game = get_object_or_404(Game, id=game_id, group=group)

    current_membership = Membership.objects.filter(group=group, user=request.user).first()
    is_allowed = current_membership is not None or request.user.is_superuser
    if not is_allowed:
        messages.error(request, "Neturite teisės peržiūrėti šio žaidimo detalių.")
        return redirect('my_groups')

    is_current_user_admin_role = (current_membership and current_membership.role == Membership.Role.ADMIN) or request.user.is_superuser

    all_memberships = group.membership_set.select_related('user').order_by('user__username')
    submitter_ids = set(Song.objects.filter(game=game).values_list('submitted_by_id', flat=True))
    voter_ids = set(Vote.objects.filter(game=game).values_list('voter_id', flat=True).distinct())

    participants_status = []
    for membership in all_memberships:
        has_submitted = membership.user.id in submitter_ids
        has_voted = membership.user.id in voter_ids
        participants_status.append({
            'user': membership.user,
            'role': membership.get_role_display(),
            'has_submitted': has_submitted,
            'has_voted': has_voted,
            'is_admin': membership.role == Membership.Role.ADMIN
        })

    context = {
        'group': group,
        'game': game,
        'participants_status': participants_status,
        'is_current_user_admin': is_current_user_admin_role,
    }
    return render(request, 'muzika_app/game_details.html', context)


@login_required
def game_voting_results_view(request, group_code, game_id):
    """ Rodo detalius balsavimo rezultatus. Leidžiama nariui arba supervartotojui. """
    group = get_object_or_404(Group, code=group_code)
    game = get_object_or_404(Game, id=game_id, group=group)

    is_member = Membership.objects.filter(group=group, user=request.user).exists()
    is_allowed = is_member or request.user.is_superuser
    if not is_allowed:
         messages.error(request, "Neturite teisės peržiūrėti šios grupės balsavimo rezultatų.")
         return redirect('my_groups')

    if not game.voting_start_date:
        messages.warning(request, "Balsavimas šiam žaidimui dar nebuvo pradėtas.")
        return redirect('game_details', group_code=group.code, game_id=game.id)

    all_votes = Vote.objects.filter(game=game).select_related(
        'voter', 'song', 'song__submitted_by'
    ).order_by('voter__username', '-points')

    voting_details = defaultdict(list)
    for vote in all_votes:
        voting_details[vote.voter].append({
            'song': vote.song,
            'points': vote.points
        })

    context = {
        'group': group,
        'game': game,
        'voting_details': dict(voting_details),
    }
    return render(request, 'muzika_app/game_voting_results.html', context)


# --- DAINŲ VALDYMAS ---

@login_required
def add_song_view(request, group_code, game_id):
    """ Leidžia pridėti dainą. Reikalinga narystė. """
    # Supervartotojas neturėtų tiesiogiai dalyvauti kaip narys (kelti dainų)
    group = get_object_or_404(Group, code=group_code)
    game = get_object_or_404(Game, id=game_id, group=group)

    try:
        membership = Membership.objects.get(group=group, user=request.user)
    except Membership.DoesNotExist:
        # Supervartotojui nerodom klaidos, bet ir neleidžiam pridėti (galima nukreipti)
        if request.user.is_superuser:
             messages.warning(request, "Supervartotojas negali kelti dainų kaip narys.")
             return redirect('group_games_list', group_code=group.code)
        else:
            messages.error(request, "Jūs nepriklausote šiai grupei.")
            return redirect('home')

    user_song = Song.objects.filter(game=game, submitted_by=request.user).first()
    is_submission_time = game.is_submission_active()
    reason_not_active = ""
    if not is_submission_time:
        now = timezone.now()
        if game.submission_start_date and now < game.submission_start_date:
            reason_not_active = f"Dainų kėlimas/redagavimas prasidės tik {game.submission_start_date.strftime('%Y-%m-%d %H:%M')}."
        elif game.submission_end_date and now > game.submission_end_date:
             reason_not_active = f"Dainų kėlimas/redagavimas baigėsi {game.submission_end_date.strftime('%Y-%m-%d %H:%M')}."
        else:
            reason_not_active = "Šiam žaidimui nenustatytas dainų kėlimo laikotarpis."

    if user_song:
        if is_submission_time:
            messages.info(request, f"Jūs jau esate įkėlę dainą '{user_song.title}'. Galite ją redaguoti.")
            return redirect('edit_song', group_code=group.code, game_id=game.id, song_id=user_song.id)
        else:
            messages.warning(request, f"Jūs jau esate įkėlę dainą, tačiau redagavimo laikas baigėsi. {reason_not_active}")
            return redirect('group_games_list', group_code=group.code)
    else:
        if not is_submission_time:
            messages.warning(request, f"Naujos dainos įkelti negalima. {reason_not_active}")
            return redirect('group_games_list', group_code=group.code)

        if request.method == 'POST':
            if Song.objects.filter(game=game, submitted_by=request.user).exists():
                 messages.error(request, "Jūs jau esate įkėlę dainą šiam žaidimui.")
                 return redirect('group_games_list', group_code=group.code)

            form = SongForm(request.POST)
            if form.is_valid():
                song = form.save(commit=False)
                song.game = game
                song.submitted_by = request.user
                try:
                     song.save()
                     messages.success(request, f'Daina "{song.title}" sėkmingai įkelta!')
                     return redirect('group_games_list', group_code=group.code)
                except IntegrityError:
                     messages.error(request, 'Klaida. Galbūt bandote įkelti dainą su YouTube nuoroda, kurią jau esate įkėlę anksčiau šiame žaidime?')
                except Exception as e:
                     messages.error(request, f"Įvyko klaida saugant dainą: {e}")
            else:
                messages.error(request, 'Formoje yra klaidų. Prašome pataisyti.')
        else:
            form = SongForm()

        context = {
            'form': form, 'group': group, 'game': game,
            'can_submit': True, 'reason': ''
        }
        return render(request, 'muzika_app/add_song.html', context)


@login_required
def edit_song_view(request, group_code, game_id, song_id):
    """ Redaguoja vartotojo įkeltą dainą. Leidžiama tik autoriui per kėlimo laikotarpį. """
    # Supervartotojas neturėtų redaguoti kitų dainų
    group = get_object_or_404(Group, code=group_code)
    game = get_object_or_404(Game, id=game_id, group=group)
    song = get_object_or_404(Song, id=song_id, game=game)

    if song.submitted_by != request.user:
        # Net jei supervartotojas, neleidžiam redaguoti ne savo dainos
        messages.error(request, "Neturite teisės redaguoti šios dainos.")
        return redirect('group_games_list', group_code=group.code)

    if not game.is_submission_active():
        messages.warning(request, f"Dainų redagavimas žaidimui '{game.name}' jau baigėsi ({game.submission_end_date.strftime('%Y-%m-%d %H:%M')}).")
        return redirect('group_games_list', group_code=group.code)

    if request.method == 'POST':
        form = SongForm(request.POST, instance=song)
        if form.is_valid():
            try:
                form.save()
                messages.success(request, f'Daina "{song.title}" sėkmingai atnaujinta!')
                return redirect('group_games_list', group_code=group.code)
            except IntegrityError:
                 messages.error(request, 'Įvyko netikėta klaida. Galbūt kita jūsų daina jau naudoja šią YouTube nuorodą?')
            except Exception as e:
                 messages.error(request, f"Įvyko klaida saugant dainą: {e}")
        else:
            messages.error(request, 'Formoje yra klaidų. Prašome pataisyti.')
    else:
        form = SongForm(instance=song)

    context = {'form': form, 'group': group, 'game': game, 'song': song}
    return render(request, 'muzika_app/edit_song.html', context)


# --- BALSAVIMAS ---

@login_required
def vote_game_view(request, group_code, game_id):
    """ Rodo balsavimo puslapį. Reikalinga narystė. """
    # Supervartotojas neturėtų balsuoti
    group = get_object_or_404(Group, code=group_code)
    game = get_object_or_404(Game, id=game_id, group=group)

    try:
        membership = Membership.objects.get(group=group, user=request.user)
    except Membership.DoesNotExist:
         if request.user.is_superuser:
             messages.warning(request, "Supervartotojas negali balsuoti kaip narys.")
             return redirect('group_games_list', group_code=group.code)
         else:
            messages.error(request, "Jūs nepriklausote šiai grupei.")
            return redirect('home')

    is_voting_time = game.is_voting_active()
    # ... (likusi balsavimo logika nepakito) ...
    reason_not_active = ""
    if not is_voting_time:
        now = timezone.now()
        if game.voting_start_date and now < game.voting_start_date:
             reason_not_active = f"Balsavimas prasidės tik {game.voting_start_date.strftime('%Y-%m-%d %H:%M')}."
        elif game.voting_end_date and now > game.voting_end_date:
             reason_not_active = f"Balsavimas baigėsi {game.voting_end_date.strftime('%Y-%m-%d %H:%M')}."
        else:
            reason_not_active = "Balsavimo laikotarpis šiam žaidimui dar nenustatytas."

    songs_to_vote_on = game.songs.exclude(submitted_by=request.user).select_related('submitted_by').order_by('?')

    # Komentaras: Nebereikia pridėti youtube_id čia, nes naudojam {% video %} žymą
    # for song in songs_to_vote_on:
    #     song.youtube_id = get_youtube_id(song.youtube_url)

    existing_votes_qs = Vote.objects.filter(game=game, voter=request.user)
    existing_votes_map = {vote.points: vote.song_id for vote in existing_votes_qs}

    submitted_data_map = {} # Tuščias POST atveju, jei nėra klaidų

    if request.method == 'POST':
        if not is_voting_time:
            messages.error(request, f"Balsuoti negalima. {reason_not_active}")
            return redirect('vote_game', group_code=group.code, game_id=game.id)

        try:
            song_id_3_points = int(request.POST.get('points_3')) if request.POST.get('points_3') else None
            song_id_2_points = int(request.POST.get('points_2')) if request.POST.get('points_2') else None
            song_id_1_point = int(request.POST.get('points_1')) if request.POST.get('points_1') else None
        except (ValueError, TypeError):
             messages.error(request, "Neteisingi balsavimo duomenys.")
             return redirect('vote_game', group_code=group.code, game_id=game.id)

        selected_song_ids = {song_id_3_points, song_id_2_points, song_id_1_point}
        selected_song_ids.discard(None)

        errors = []
        if len(selected_song_ids) != 3:
            errors.append("Turite pasirinkti tris skirtingas dainas ir joms priskirti 1, 2 ir 3 taškus.")

        valid_song_ids = set(songs_to_vote_on.values_list('id', flat=True))
        for selected_id in selected_song_ids:
            if selected_id not in valid_song_ids:
                 errors.append(f"Pasirinkta daina (ID: {selected_id}) nepriklauso šiam žaidimui arba yra jūsų.")
                 break

        if errors:
            for error in errors: messages.error(request, error)
            # Išsaugom pateiktus duomenis, kad būtų galima atstatyti formoje
            submitted_data_map = {
                'points_3': request.POST.get('points_3'), # Gaunam kaip stringą
                'points_2': request.POST.get('points_2'),
                'points_1': request.POST.get('points_1'),
            }
        else:
            # --- Balsų Išsaugojimas ---
            try:
                with transaction.atomic():
                    Vote.objects.filter(game=game, voter=request.user).delete()
                    votes_to_create = []
                    if song_id_3_points: votes_to_create.append(Vote(game=game, voter=request.user, song_id=song_id_3_points, points=3))
                    if song_id_2_points: votes_to_create.append(Vote(game=game, voter=request.user, song_id=song_id_2_points, points=2))
                    if song_id_1_point: votes_to_create.append(Vote(game=game, voter=request.user, song_id=song_id_1_point, points=1))
                    Vote.objects.bulk_create(votes_to_create)
                messages.success(request, "Jūsų balsai sėkmingai išsaugoti!")
                return redirect('group_games_list', group_code=group.code) # Pakeista iš group_admin
            except ValidationError as e: messages.error(request, f"Klaida saugant balsus: {'; '.join(e.messages)}")
            except IntegrityError as e: messages.error(request, f"Klaida saugant balsus: {e}. Galbūt bandėte balsuoti kelis kartus?")
            except Exception as e: messages.error(request, f"Įvyko netikėta klaida saugant balsus: {e}")
            # Jei įvyko klaida saugant, išsaugom pateiktus duomenis
            submitted_data_map = {
                'points_3': request.POST.get('points_3'),
                'points_2': request.POST.get('points_2'),
                'points_1': request.POST.get('points_1'),
            }

    # --- GET arba POST su klaidomis ---
    context = {
        'group': group, 'game': game, 'songs': songs_to_vote_on,
        'is_voting_time': is_voting_time, 'reason_not_active': reason_not_active,
        'existing_votes_map': existing_votes_map,
        'submitted_data': submitted_data_map # Perduodam pateiktus duomenis (gali būti tuščias dict)
    }
    return render(request, 'muzika_app/vote_game.html', context)


@login_required
@require_POST
def start_voting_view(request, group_code, game_id):
    """ Rankiniu būdu pradeda balsavimą. Leidžiama adminui arba supervartotojui. """
    group = get_object_or_404(Group, code=group_code)
    game = get_object_or_404(Game, id=game_id, group=group)
    now = timezone.now()

    is_allowed = request.user.is_superuser or Membership.objects.filter(group=group, user=request.user, role=Membership.Role.ADMIN).exists()
    if not is_allowed:
        messages.error(request, "Tik grupės administratoriai (arba supervartotojas) gali skelbti balsavimą.")
        return redirect('group_games_list', group_code=group.code) # Pakeista iš group_admin

    if game.is_voting_finished():
        messages.warning(request, f'Balsavimas žaidimui "{game.name}" jau yra pasibaigęs.')
        return redirect('group_games_list', group_code=group.code)

    if not game.voting_end_date or game.voting_end_date <= now:
        messages.error(request, "Negalima pradėti balsavimo, kol žaidimui nenustatyta balsavimo pabaigos data ateityje.")
        return redirect('group_games_list', group_code=group.code)

    try:
        update_fields_list = []
        if not game.submission_end_date or game.submission_end_date > now:
            game.submission_end_date = now
            update_fields_list.append('submission_end_date')
        if game.voting_start_date != now: # Tikrinam ar tikrai reikia keisti
             game.voting_start_date = now
             update_fields_list.append('voting_start_date')
        if update_fields_list:
             game.save(update_fields=update_fields_list)
             messages.success(request, f'Balsavimas žaidimui "{game.name}" sėkmingai paskelbtas!')
        else:
             messages.info(request, f'Balsavimas žaidimui "{game.name}" jau buvo paskelbtas anksčiau.')
    except Exception as e:
        messages.error(request, f"Įvyko klaida bandant paskelbti balsavimą: {e}")

    return redirect('group_games_list', group_code=group.code)


@login_required
@require_POST
def calculate_game_results_view(request, group_code, game_id):
    """ Skaičiuoja rezultatus. Leidžiama adminui arba supervartotojui. """
    group = get_object_or_404(Group, code=group_code)
    game = get_object_or_404(Game, id=game_id, group=group)

    is_allowed = request.user.is_superuser or Membership.objects.filter(group=group, user=request.user, role=Membership.Role.ADMIN).exists()
    if not is_allowed:
        messages.error(request, "Tik grupės administratoriai (arba supervartotojas) gali skaičiuoti rezultatus.")
        return redirect('game_details', group_code=group.code, game_id=game.id) # Grįžtam į detales

    if game.winners.exists():
        messages.info(request, "Šio žaidimo rezultatai jau buvo apskaičiuoti anksčiau.")
        return redirect('game_details', group_code=group.code, game_id=game.id)

    memberships = Membership.objects.filter(group=group)
    group_member_ids = set(memberships.values_list('user_id', flat=True))
    voter_ids = set(Vote.objects.filter(game=game).values_list('voter_id', flat=True).distinct())
    if not (group_member_ids == voter_ids and len(group_member_ids) > 0):
         if not game.is_voting_finished():
             messages.warning(request, "Dar ne visi nariai balsavo. Rezultatų skaičiuoti negalima.")
             return redirect('group_admin', group_code=group.code)

    winners_found = []
    now = timezone.now()
    try:
        with transaction.atomic():
            results = Song.objects.filter(game=game) \
                            .annotate(total_points=Sum('votes__points')) \
                            .filter(total_points__isnull=False) \
                            .select_related('submitted_by') \
                            .order_by('-total_points')
            if results.exists():
                max_points = results.first().total_points
                if max_points > 0:
                    winning_songs = results.filter(total_points=max_points)
                    winning_users = [song.submitted_by for song in winning_songs if song.submitted_by]
                    if winning_users:
                        unique_winning_users = list(set(winning_users))
                        game.winners.add(*unique_winning_users)
                        winners_found = unique_winning_users

            if game.voting_end_date and now < game.voting_end_date:
                game.voting_end_date = now
                game.save(update_fields=['voting_end_date'])

        if winners_found:
             winner_names = ", ".join([(w.get_full_name() or w.username) for w in winners_found])
             messages.success(request, f'Rezultatai apskaičiuoti! Laimėtojas(-ai): {winner_names}.')
        else:
             messages.warning(request, "Rezultatai apskaičiuoti, tačiau laimėtojų nustatyti nepavyko (galbūt niekas nebalsavo?).")
    except Exception as e:
        messages.error(request, f"Įvyko klaida skaičiuojant rezultatus: {e}")

    return redirect('group_admin', group_code=group.code) # Nukreipiam į admin, kad matytųsi laimėtojas


# --- STATISTIKA ---

@login_required
def statistics_view(request, group_code):
    """ Rodo grupės statistiką. Leidžiama nariui arba supervartotojui. """
    group = get_object_or_404(Group, code=group_code)
    now = timezone.now()

    is_member = Membership.objects.filter(group=group, user=request.user).exists()
    is_allowed = is_member or request.user.is_superuser
    if not is_allowed:
         messages.error(request, "Neturite teisės peržiūrėti šios grupės statistikos.")
         return redirect('my_groups')

    group_member_ids = list(Membership.objects.filter(group=group).values_list('user_id', flat=True))

    top_winners_qs = User.objects.filter(id__in=group_member_ids).annotate(
        num_wins=Count('won_games', distinct=True, filter=models.Q(won_games__group=group))
    ).filter(num_wins__gt=0).order_by('-num_wins')
    top_winners = list(top_winners_qs)

    points_ranking_qs = User.objects.filter(id__in=group_member_ids).annotate(
        total_score_received=Sum(
            'submitted_songs__votes__points',
             filter=models.Q(
                 submitted_songs__game__group=group,
                 submitted_songs__game__voting_end_date__isnull=False,
                 submitted_songs__game__voting_end_date__lte=now
             )
        )
    ).filter(
        total_score_received__isnull=False, total_score_received__gt=0
    ).order_by('-total_score_received')

    points_ranking_list = list(points_ranking_qs)
    for user_stat in points_ranking_list:
        user_stat.score_ending = get_lithuanian_score_ending(user_stat.total_score_received)

    context = {
        'group': group,
        'top_winners': top_winners,
        'points_ranking': points_ranking_list,
    }
    return render(request, 'muzika_app/statistics.html', context)


# --- PASKYROS VALDYMAS ---

@login_required
def profile_edit_view(request):
    """ Rodo ir tvarko profilio redagavimo formas. """
    user = request.user
    profile_form = UserProfileEditForm(instance=user)
    password_form = PasswordChangeForm(user=user)

    if request.method == 'POST':
        if 'update_profile' in request.POST:
            profile_form = UserProfileEditForm(request.POST, instance=user)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Profilio duomenys sėkmingai atnaujinti!')
                return redirect('profile_edit')
            else:
                 messages.error(request, 'Klaida atnaujinant profilio duomenis. Patikrinkite laukus.')
                 password_form = PasswordChangeForm(user=user)
        elif 'change_password' in request.POST:
            password_form = PasswordChangeForm(user=user, data=request.POST)
            if password_form.is_valid():
                user = password_form.save()
                update_session_auth_hash(request, user)
                messages.success(request, 'Slaptažodis sėkmingai pakeistas!')
                return redirect('profile_edit')
            else:
                messages.error(request, 'Klaida keičiant slaptažodį. Patikrinkite laukus.')
                profile_form = UserProfileEditForm(instance=user)

    context = {
        'profile_form': profile_form,
        'password_form': password_form
    }
    return render(request, 'muzika_app/profile_edit.html', context)


# --- SUPERVARTOTOJO FUNKCIJOS (PASIRINKTINAI) ---

@staff_member_required # Reikalauja is_staff=True arba is_superuser=True
def all_groups_view(request):
    """ Rodo visų sistemos grupių sąrašą (tik personalui/supervartotojui). """
    if not request.user.is_superuser: # Papildomas tikrinimas specifiškai supervartotojui
        messages.error(request, "Neturite teisės peržiūrėti šio puslapio.")
        return redirect('home')

    all_groups = Group.objects.select_related('creator').all().order_by('name') # Optimizuojam
    context = {'all_groups': all_groups}
    return render(request, 'muzika_app/all_groups.html', context)

@login_required
@require_POST # Leidžiame tik POST užklausas šiam veiksmui
def join_group_view(request):
    """ Apdoroja grupės prisijungimo formos pateikimą (iš modalinio lango)."""
    group_code = request.POST.get('group_code', '').strip().upper() # Gaunam kodą

    if not group_code:
        messages.error(request, 'Grupės kodas negali būti tuščias.')
        # Nukreipiam į puslapį, iš kurio atėjo forma (Mano grupės)
        return redirect('my_groups')

    try:
        group_to_join = Group.objects.get(code=group_code)
    except Group.DoesNotExist:
        messages.error(request, f'Grupė su kodu "{group_code}" nerasta.')
        return redirect('my_groups')

    # Patikrinam, ar vartotojas jau nėra šios grupės narys
    is_already_member = Membership.objects.filter(group=group_to_join, user=request.user).exists()

    if is_already_member:
        messages.info(request, f'Jūs jau esate grupės "{group_to_join.name}" narys.')
        # Nukreipiam į tos grupės admin puslapį
        return redirect('group_admin', group_code=group_to_join.code)
    else:
        # Sukuriam naują narystę su MEMBER role
        try:
            Membership.objects.create(
                group=group_to_join,
                user=request.user,
                role=Membership.Role.MEMBER
            )
            messages.success(request, f'Sėkmingai prisijungėte prie grupės "{group_to_join.name}"!')
             # Nukreipiam į prisijungtos grupės admin puslapį
            return redirect('group_admin', group_code=group_to_join.code)
        except Exception as e:
            messages.error(request, f'Įvyko klaida bandant prisijungti prie grupės: {e}')
            return redirect('my_groups')

@staff_member_required # Reikalauja is_staff=True arba is_superuser=True
def all_groups_view(request):
    """ Rodo visų sistemos grupių sąrašą (tik personalui/supervartotojui). """
    # Galima pridėti papildomą patikrinimą tik supervartotojui, jei norite griežčiau
    if not request.user.is_superuser:
        messages.error(request, "Neturite teisės peržiūrėti šio puslapio.")
        return redirect('home') # Arba 'my_groups'

    all_groups = Group.objects.select_related('creator').all().order_by('name')
    context = {
        'all_groups': all_groups,
        'is_superuser_page': True # Galima pridėti flag'ą spec. stiliams ar logikai šablone
    }
    return render(request, 'muzika_app/all_groups.html', context)

@login_required
@require_POST # Tik POST metodas leidžiamas trynimui
def delete_group_view(request, group_code):
    """ Trina grupę ir visus susijusius duomenis. Leidžiama TIK supervartotojui. """

    # --- GRIEŽTAS SUPERVARTOTOJO PATIKRINIMAS ---
    if not request.user.is_superuser:
        messages.error(request, "Neturite teisės trinti grupių.")
        # Nukreipiam į pagrindinį puslapį arba mano grupes
        return redirect('home')
    # --- PABAIGA ---

    group = get_object_or_404(Group, code=group_code)

    try:
        group_name = group.name # Išsaugom pavadinimą pranešimui
        group.delete() # Ištrinam grupę (CASCADE ištrins susijusius objektus)
        messages.success(request, f'Grupė "{group_name}" ir visi susiję duomenys sėkmingai ištrinti.')
    except Exception as e:
        messages.error(request, f"Įvyko klaida trinant grupę '{group.name}': {e}")

    # Po trynimo grįžtame į visų grupių sąrašą
    return redirect('all_groups_list')

@login_required
@require_POST # Tik POST metodas
def toggle_game_creation_view(request, group_code):
    """ Perjungia grupės 'can_create_games' atributą. Tik supervartotojui. """
    if not request.user.is_superuser:
        messages.error(request, "Neturite teisės keisti šio nustatymo.")
        # Nukreipiam atgal, iš kur galėjo ateiti (pvz., home arba my_groups)
        # Kadangi mygtukas bus all_groups, nukreipiam ten
        # return redirect('home')
        # Reikia patikrinti, ar all_groups_list egzistuoja, gal nukreipti į my_groups?
        # Saugiausias variantas - į my_groups
        return redirect('my_groups')

    group = get_object_or_404(Group, code=group_code)

    try:
        # Perjungiam reikšmę
        group.can_create_games = not group.can_create_games
        group.save(update_fields=['can_create_games']) # Išsaugom tik pakeistą lauką
        if group.can_create_games:
            messages.success(request, f"Grupėje '{group.name}' žaidimų kūrimas ĮJUNGTAS.")
        else:
            messages.warning(request, f"Grupėje '{group.name}' žaidimų kūrimas IŠJUNGTAS.")
    except Exception as e:
        messages.error(request, f"Klaida keičiant nustatymą grupei '{group.name}': {e}")

    # Grįžtame į visų grupių sąrašą
    return redirect('all_groups_list')