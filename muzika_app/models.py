from django.db import models
from django.conf import settings # Importuojame settings, kad gautume AUTH_USER_MODEL
import random
import string
from django.core.exceptions import ValidationError
from django.utils import timezone

# Naudojame settings.AUTH_USER_MODEL vietoj tiesioginio User importo - tai geresnė praktika
# Jei nenaudojate custom vartotojo modelio, tai bus 'auth.User'
AUTH_USER_MODEL = settings.AUTH_USER_MODEL

def generate_unique_code():
    """Generuoja unikalų 7 simbolių kodą grupei."""
    length = 7
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
        if Group.objects.filter(code=code).count() == 0:
            break
    return code

class Group(models.Model):
    # ... (kiti laukai: code, name, information, created_at, creator, members) ...
    code = models.CharField(max_length=7, default=generate_unique_code, unique=True, editable=False)
    name = models.CharField(max_length=100, verbose_name="Grupės pavadinimas", null=True)
    information = models.TextField(blank=True, null=True, verbose_name="Informacija")
    created_at = models.DateTimeField(auto_now_add=True)
    creator = models.ForeignKey(
        AUTH_USER_MODEL,
        related_name='created_groups',
        on_delete=models.SET_NULL,
        null=True, blank=True
    )
    members = models.ManyToManyField(
        AUTH_USER_MODEL,
        related_name='joined_groups',
        blank=True
    )

    # <<< NAUJAS LAUKAS >>>
    can_create_games = models.BooleanField(
        default=True,
        verbose_name="Leisti kurti žaidimus?",
        help_text="Pažymėkite, jei grupės administratoriai (arba laimėtojai) gali kurti naujus žaidimus šioje grupėje."
    )
    # <<< PABAIGA >>>

    def __str__(self):
        return f"{self.name} ({self.code})"

class Membership(models.Model):
    # Rolės pasirinkimai
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Administratorius'
        MEMBER = 'MEMBER', 'Narys'

    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    user = models.ForeignKey(AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.MEMBER, # Numatytoji rolė - Narys
        verbose_name="Rolė"
    )
    date_joined = models.DateTimeField(auto_now_add=True)

    class Meta:
        # Užtikrinama, kad vartotojas negali būti tos pačios grupės nariu kelis kartus
        unique_together = ('group', 'user')
        ordering = ['date_joined'] # Galima rikiuoti pagal prisijungimo datą

    def __str__(self):
        return f"{self.user.username} - {self.group.name} ({self.get_role_display()})"

class Game(models.Model):
    group = models.ForeignKey(
        Group,
        on_delete=models.CASCADE,
        related_name='games',        verbose_name="Grupė"
    )
    name = models.CharField(
        max_length=150,
        verbose_name="Žaidimo tema / pavadinimas"
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name="Žaidimo aprašymas"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Sukūrimo data"
    )
    creator = models.ForeignKey(
         AUTH_USER_MODEL,
         on_delete=models.SET_NULL,
         null=True,
         blank=True,
         related_name='created_games',
         verbose_name="Žaidimo kūrėjas"
     )
    submission_start_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Dainų kėlimo pradžia"
    )
    submission_end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Dainų kėlimo pabaiga"
    )
    voting_start_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Balsavimo pradžia"
    )
    voting_end_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Balsavimo pabaiga"
    )
    winners = models.ManyToManyField(
        AUTH_USER_MODEL,
        related_name='won_games', # Kaip pasiekti laimėtus žaidimus iš User: user.won_games.all()
        blank=True,              # Leidžiama neturėti laimėtojų (pvz., kol nesuskaičiuota)
        verbose_name="Laimėtojai"
    )

    class Meta:
        ordering = ['-created_at']
        verbose_name = "Žaidimas"
        verbose_name_plural = "Žaidimai"

    def __str__(self):
        return f"{self.name} (Grupė: {self.group.name})"

    def is_submission_active(self):
        # ... (is_submission_active metodas) ...
        now = timezone.now()
        if self.submission_start_date and self.submission_end_date:
            return self.submission_start_date <= now <= self.submission_end_date
        return False

    def is_voting_active(self):
        # ... (is_voting_active metodas) ...
        now = timezone.now()
        if self.voting_start_date and self.voting_end_date:
            return self.voting_start_date <= now <= self.voting_end_date
        return False

    def is_voting_finished(self):
        """ Patikrina, ar balsavimas jau pasibaigęs."""
        now = timezone.now() # Įsitikinkite, kad 'timezone' importuotas failo viršuje
        return self.voting_end_date and self.voting_end_date <= now

    def are_results_calculated(self):
        """ Patikrina, ar laimėtojai jau yra priskirti. """
        # Tikrinam, ar voting_end_date praėjo IR ar winners sąrašas ne tuščias
        # Arba galima pridėti papildomą BooleanField 'results_published'
        return self.is_voting_finished() and self.winners.exists()

class Song(models.Model):
    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE, # Ištrynus žaidimą, ištrinamos ir jam priskirtos dainos
        related_name='songs',     # Kaip pasiekti dainas iš žaidimo: game.songs.all()
        verbose_name="Žaidimas"
    )
    submitted_by = models.ForeignKey(
        AUTH_USER_MODEL,
        on_delete=models.CASCADE, # Ištrynus vartotoją, ištrinamos ir jo keltos dainos (?)
                                  # Galima keisti į SET_NULL, jei norite palikti dainas
        related_name='submitted_songs',
        verbose_name="Įkėlė"
    )
    title = models.CharField(
        max_length=200,
        verbose_name="Dainos pavadinimas"
    )
    youtube_url = models.URLField(
        max_length=255,
        verbose_name="YouTube nuoroda"
    )
    submitted_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Įkėlimo data"
    )

    class Meta:
        ordering = ['submitted_at'] # Rikiuojame pagal įkėlimo datą (seniausios viršuje?)
                                    # Galima keisti į '-submitted_at' naujausioms viršuje
        verbose_name = "Daina"
        verbose_name_plural = "Dainos"
        # Užtikrinam, kad tas pats vartotojas negali įkelti tos pačios nuorodos tam pačiam žaidimui
        unique_together = ('game', 'submitted_by', 'youtube_url')

    def __str__(self):
        return f'"{self.title}" (Žaidimas: {self.game.name}, Įkėlė: {self.submitted_by.username})'

class Vote(models.Model):
    POINTS_CHOICES = [
        (5, '5 taškai'),
        (4, '4 taškai'),
        (3, '3 taškai'),
        (2, '2 taškai'),
        (1, '1 taškas'),
    ]

    game = models.ForeignKey(
        Game,
        on_delete=models.CASCADE,
        related_name='votes',
        verbose_name="Žaidimas"
    )
    song = models.ForeignKey(
        Song,
        on_delete=models.CASCADE,
        related_name='votes',
        verbose_name="Daina"
    )
    voter = models.ForeignKey(
        AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='votes_cast',
        verbose_name="Balsuotojas"
    )
    points = models.PositiveSmallIntegerField(
        choices=POINTS_CHOICES,
        verbose_name="Taškai"
    )
    voted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Balsas"
        verbose_name_plural = "Balsai"
        ordering = ['-voted_at']
        # Apribojimai:
        # 1. Vienas vartotojas tam pačiam žaidimui negali skirti tų pačių taškų kelioms dainoms
        unique_together = [
            ('game', 'voter', 'points'),
        # 2. Vienas vartotojas už tą pačią dainą tam pačiam žaidimui gali balsuoti tik kartą (su vienu taškų skaičiumi)
            ('game', 'voter', 'song')
        ]

    def __str__(self):
        return f"{self.voter.username} skyrė {self.points} tšk. dainai '{self.song.title}' žaidime '{self.game.name}'"

    # Papildoma modelio lygio validacija (neprivaloma, bet naudinga)
    def clean(self):
        super().clean()
        # Tikrinam, ar nebalsuojama už savo dainą
        if self.song.submitted_by == self.voter:
            raise ValidationError("Negalima balsuoti už savo įkeltą dainą.")
        # Tikrinam, ar daina priklauso tam pačiam žaidimui, už kurį balsuojama
        if self.song.game != self.game:
             raise ValidationError("Ši daina nepriklauso žaidimui, už kurį balsuojate.")








