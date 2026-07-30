import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from muzika_app.models import Group, Membership, Game, Song, Vote

User = get_user_model()

# Realios YouTube nuorodos testavimui – parinktos tokios, kurias
# leidžiama įterpti (embed) kituose puslapiuose (daugiausia NCS ir
# kūrėjai, kurie neblokuoja įterpimo).
YOUTUBE_URLS = [
    ("Rick Astley - Never Gonna Give You Up", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
    ("Alan Walker - Faded", "https://www.youtube.com/watch?v=60ItHLz5WEA"),
    ("Alan Walker - Alone", "https://www.youtube.com/watch?v=1-xGerv5FOk"),
    ("Alan Walker - Spectre (NCS)", "https://www.youtube.com/watch?v=AOeY-nDp7hI"),
    ("Cartoon - On & On (NCS)", "https://www.youtube.com/watch?v=K4DyBUG242c"),
    ("Elektronomia - Sky High (NCS)", "https://www.youtube.com/watch?v=TW9d8vYrVFQ"),
    ("Janji - Heroes Tonight (NCS)", "https://www.youtube.com/watch?v=3nQNiWdeH2Q"),
    ("Jim Yosef - Firefly (NCS)", "https://www.youtube.com/watch?v=K-i1Up3fDgo"),
    ("DEAF KEV - Invincible (NCS)", "https://www.youtube.com/watch?v=J2X5mJ3HDYE"),
    ("Tobu - Hope (NCS)", "https://www.youtube.com/watch?v=EP625xQIGzs"),
    ("Different Heaven - Nekozilla (NCS)", "https://www.youtube.com/watch?v=e7dp0NBmc6c"),
    ("Elektronomia - Energy (NCS)", "https://www.youtube.com/watch?v=cJc3ncFO2f0"),
    ("Marshmello - Alone", "https://www.youtube.com/watch?v=ALZHF5UqnU4"),
    ("Culture Code - Make Me Move (NCS)", "https://www.youtube.com/watch?v=vBGiFtb8Rpw"),
    ("Lensko - Cetus (NCS)", "https://www.youtube.com/watch?v=z1oHQjci9uY"),
    ("Ship Wrek & Zookeepers - Ark (NCS)", "https://www.youtube.com/watch?v=cKopMt7ktBk"),
]

GAME_THEMES = [
    ("80-ųjų hitai", "Geriausios dešimtojo dešimtmečio dainos, kurios vis dar skamba."),
    ("Vasaros nuotaika", "Dainos, kurios primena saulę, paplūdimį ir atostogas."),
    ("Roko klasika", "Legendinės roko dainos visų laikų."),
    ("Šokių aikštelė", "Dainos, po kurių neįmanoma nustovėti vietoje."),
    ("Nostalgija", "Dainos, kurios grąžina į praeitį."),
]

USERS = [
    ("jonas", "Jonas", "Jonaitis"),
    ("petras", "Petras", "Petraitis"),
    ("ona", "Ona", "Onaitė"),
    ("ruta", "Rūta", "Rutaitė"),
    ("tomas", "Tomas", "Tomaitis"),
    ("lina", "Lina", "Linaitė"),
]


class Command(BaseCommand):
    help = "Sugeneruoja testinius duomenis: vartotojus, grupę ir praėjusius žaidimus su dainomis bei balsais."

    def add_arguments(self, parser):
        parser.add_argument(
            "--games",
            type=int,
            default=3,
            help="Kiek praėjusių žaidimų sukurti (numatytoji 3).",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Prieš generuojant ištrinti anksčiau sukurtus testinius duomenis.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        num_games = options["games"]
        password = "testas123"

        if options["clear"]:
            self._clear_test_data()

        # 1. Vartotojai
        users = []
        for username, first, last in USERS:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "email": f"{username}@example.com",
                },
            )
            if created:
                user.set_password(password)
                user.save()
                self.stdout.write(self.style.SUCCESS(f"Sukurtas vartotojas: {username}"))
            else:
                self.stdout.write(f"Vartotojas jau egzistuoja: {username}")
            users.append(user)

        # 2. Grupė
        group, created = Group.objects.get_or_create(
            name="Testinė grupė",
            defaults={
                "information": "Automatiškai sugeneruota testinė grupė.",
                "creator": users[0],
                "can_create_games": True,
            },
        )
        group.members.add(*users)
        for i, user in enumerate(users):
            role = Membership.Role.ADMIN if i == 0 else Membership.Role.MEMBER
            Membership.objects.get_or_create(
                group=group,
                user=user,
                defaults={"role": role},
            )
        self.stdout.write(
            self.style.SUCCESS(f"Grupė paruošta: {group.name} (kodas: {group.code})")
        )

        # 3. Praėję žaidimai su dainomis ir balsais
        now = timezone.now()
        for g in range(num_games):
            theme, desc = GAME_THEMES[g % len(GAME_THEMES)]
            # Kiekvienas žaidimas vis senesnis
            weeks_ago = (g + 1) * 2
            sub_start = now - timedelta(weeks=weeks_ago, days=7)
            sub_end = now - timedelta(weeks=weeks_ago, days=3)
            vote_start = sub_end
            vote_end = now - timedelta(weeks=weeks_ago)

            game = Game.objects.create(
                group=group,
                name=f"{theme} #{g + 1}",
                description=desc,
                creator=users[0],
                submission_start_date=sub_start,
                submission_end_date=sub_end,
                voting_start_date=vote_start,
                voting_end_date=vote_end,
            )
            self.stdout.write(self.style.SUCCESS(f"  Sukurtas žaidimas: {game.name}"))

            # Kiekvienas vartotojas įkelia po vieną dainą
            songs = []
            available = random.sample(YOUTUBE_URLS, len(users))
            for user, (title, url) in zip(users, available):
                song = Song.objects.create(
                    game=game,
                    submitted_by=user,
                    title=title,
                    youtube_url=url,
                )
                songs.append(song)

            # Balsavimas: kiekvienas skiria 5-4-3-2-1 taškus kitų dainoms
            self._generate_votes(game, users, songs)

            # Laimėtojai pagal surinktus taškus
            self._assign_winners(game, songs)

        self.stdout.write(self.style.SUCCESS("\nTestiniai duomenys sėkmingai sugeneruoti!"))
        self.stdout.write(f"Prisijungimo slaptažodis visiems vartotojams: {password}")

    def _generate_votes(self, game, users, songs):
        points_scale = [5, 4, 3, 2, 1]
        for voter in users:
            # Dainos, už kurias galima balsuoti (ne savo)
            other_songs = [s for s in songs if s.submitted_by_id != voter.id]
            if not other_songs:
                continue
            random.shuffle(other_songs)
            # Kiek taškų galima paskirstyti
            count = min(len(points_scale), len(other_songs))
            for points, song in zip(points_scale[:count], other_songs[:count]):
                Vote.objects.create(
                    game=game,
                    song=song,
                    voter=voter,
                    points=points,
                )

    def _assign_winners(self, game, songs):
        # Suskaičiuojame taškus kiekvienai dainai
        scored = []
        for song in songs:
            total = sum(v.points for v in song.votes.all())
            scored.append((total, song))
        if not scored:
            return
        max_score = max(total for total, _ in scored)
        if max_score == 0:
            return
        winners = [song.submitted_by for total, song in scored if total == max_score]
        game.winners.add(*winners)
        names = ", ".join(w.username for w in winners)
        self.stdout.write(f"    Laimėtojas(-ai): {names} ({max_score} tšk.)")

    def _clear_test_data(self):
        usernames = [u[0] for u in USERS]
        Group.objects.filter(name="Testinė grupė").delete()
        User.objects.filter(username__in=usernames).delete()
        self.stdout.write(self.style.WARNING("Anksčiau sukurti testiniai duomenys ištrinti."))
