import random
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from muzika_app.models import Group, Membership, Game, Song

User = get_user_model()

# Embed'inamos (leidziancios iterpima) YouTube nuorodos testavimui.
YOUTUBE_URLS = [
    ("Alan Walker - Faded", "https://www.youtube.com/watch?v=60ItHLz5WEA"),
    ("Alan Walker - Spectre (NCS)", "https://www.youtube.com/watch?v=AOeY-nDp7hI"),
    ("Cartoon - On & On (NCS)", "https://www.youtube.com/watch?v=K4DyBUG242c"),
    ("Elektronomia - Sky High (NCS)", "https://www.youtube.com/watch?v=TW9d8vYrVFQ"),
    ("Janji - Heroes Tonight (NCS)", "https://www.youtube.com/watch?v=3nQNiWdeH2Q"),
    ("Jim Yosef - Firefly (NCS)", "https://www.youtube.com/watch?v=K-i1Up3fDgo"),
    ("DEAF KEV - Invincible (NCS)", "https://www.youtube.com/watch?v=J2X5mJ3HDYE"),
    ("Tobu - Hope (NCS)", "https://www.youtube.com/watch?v=EP625xQIGzs"),
]

USERS = [
    ("jonas", "Jonas", "Jonaitis"),
    ("petras", "Petras", "Petraitis"),
    ("ona", "Ona", "Onaite"),
    ("ruta", "Ruta", "Rutaite"),
    ("tomas", "Tomas", "Tomaitis"),
    ("lina", "Lina", "Linaite"),
]


class Command(BaseCommand):
    help = (
        "Sugeneruoja zaidima, kuris SIUO METU yra balsavimo stadijoje "
        "(dainos jau ikeltos, balsavimas atviras)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--group",
            type=str,
            default="Testine grupe",
            help="Grupes, i kuria deti zaidima, pavadinimas.",
        )
        parser.add_argument(
            "--name",
            type=str,
            default="Aktyvus balsavimas",
            help="Zaidimo pavadinimas.",
        )
        parser.add_argument(
            "--songs",
            type=int,
            default=6,
            help="Kiek dainu ikelti (numatytoji 6).",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = "testas123"
        group_name = options["group"]
        game_name = options["name"]
        num_songs = options["songs"]

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
            users.append(user)

        # 2. Grupe
        group, _ = Group.objects.get_or_create(
            name=group_name,
            defaults={
                "information": "Automatiskai sugeneruota testine grupe.",
                "creator": users[0],
                "can_create_games": True,
            },
        )
        group.members.add(*users)
        for i, user in enumerate(users):
            role = Membership.Role.ADMIN if i == 0 else Membership.Role.MEMBER
            Membership.objects.get_or_create(
                group=group, user=user, defaults={"role": role}
            )
        self.stdout.write(
            self.style.SUCCESS(f"Grupe paruosta: {group.name} (kodas: {group.code})")
        )

        # 3. Zaidimas balsavimo stadijoje:
        #    - dainu kelimas prasidejo pries savaite ir JAU pasibaige (vakar)
        #    - balsavimas prasidejo vakar ir baigsis po 3 dienu
        now = timezone.now()
        sub_start = now - timedelta(days=7)
        sub_end = now - timedelta(days=1)      # kelimas pasibaiges
        vote_start = sub_end                    # balsavimo pradzia = kelimo pabaiga
        vote_end = now + timedelta(days=3)      # balsavimas dar atviras

        game = Game.objects.create(
            group=group,
            name=game_name,
            description="Sis zaidimas siuo metu yra balsavimo stadijoje - galima balsuoti!",
            creator=users[0],
            submission_start_date=sub_start,
            submission_end_date=sub_end,
            voting_start_date=vote_start,
            voting_end_date=vote_end,
        )
        self.stdout.write(self.style.SUCCESS(f"Sukurtas zaidimas: {game.name} (ID: {game.id})"))

        # 4. Dainos - kiekvienas vartotojas ikelia po viena
        count = min(num_songs, len(users), len(YOUTUBE_URLS))
        chosen = random.sample(YOUTUBE_URLS, count)
        for user, (title, url) in zip(users[:count], chosen):
            Song.objects.create(
                game=game,
                submitted_by=user,
                title=title,
                youtube_url=url,
            )
            self.stdout.write(f"  + Daina: {title} (ikele {user.username})")

        # Samoningai NEgeneruojame balsu - kad galetum pats balsuoti.
        self.stdout.write(self.style.SUCCESS(
            f"\nZaidimas '{game.name}' paruostas balsavimui!"
        ))
        self.stdout.write(f"Balsavimas atviras iki: {vote_end:%Y-%m-%d %H:%M}")
        self.stdout.write(f"Grupes kodas: {group.code}")
        self.stdout.write(f"Prisijungimo slaptazodis visiems vartotojams: {password}")
