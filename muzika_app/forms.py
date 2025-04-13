from django import forms
from .models import Group, Game, Song
from django.contrib.auth.forms import UserCreationForm, UsernameField, UsernameField, PasswordChangeForm
from django.contrib.auth import get_user_model
from django.db import transaction

User = get_user_model()

class GroupForm(forms.ModelForm):
    class Meta:
        model = Group
        fields = ['name', 'information'] # Įtraukiame tik šiuos laukus į formą
        widgets = {
            'name': forms.TextInput(attrs={'class': 'mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-gray-100'}),
            'information': forms.Textarea(attrs={'rows': 3, 'class': 'mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-gray-100'}),
        }
        labels = {
            'name': 'Grupės pavadinimas',
            'information': 'Papildoma informacija (nebūtina)',
        }

class SignUpForm(UserCreationForm):
    # ... (formos laukų password1, password2, email, first_name, last_name apibrėžimai lieka tokie patys) ...
    password1 = forms.CharField(
        label="Slaptažodis",
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class': 'mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-gray-100'}),
        help_text="",
    )
    password2 = forms.CharField(
        label="Pakartokite slaptažodį",
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class': 'mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-gray-100'}),
        help_text="Įveskite tą patį slaptažodį kaip ir pirmą kartą, patikrinimui.",
    )
    email = forms.EmailField(
        label="El. pašto adresas",
        max_length=254, required=True,
        widget=forms.EmailInput(attrs={'autocomplete': 'email', 'class': 'mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-gray-100'})
    )
    first_name = forms.CharField(
        label="Vardas",
        max_length=150, required=False,
        widget=forms.TextInput(attrs={'autocomplete': 'given-name', 'class': 'mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-gray-100'})
        )
    last_name = forms.CharField(
        label="Pavardė",
        max_length=150, required=False,
        widget=forms.TextInput(attrs={'autocomplete': 'family-name', 'class': 'mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-gray-100'})
        )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name")
        field_classes = {"username": UsernameField}
        widgets = {
             'username': forms.TextInput(attrs={'autocomplete': 'username', 'class': 'mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-gray-100'}),
        }
        labels = { 'username': 'Prisijungimo vardas' }
        # --- PATAISYTA DALIS ---
        help_texts = {
            'username': 'Privalomas. 150 simbolių ar mažiau. Leidžiamos tik raidės, skaičiai ir @/./+/-/_ ženklai.'
        } # <-- Įsitikinkite, kad čia yra uždarantys riestiniai skliaustai ir nėra žodžio 'return' prieš 'username'
        # --- PATAISYMO PABAIGA ---

    # ... (save() metodas lieka toks pat) ...
    @transaction.atomic
    def save(self, commit=True):
        user = super().save(commit=False)
        user.first_name = self.cleaned_data.get("first_name", "")
        user.last_name = self.cleaned_data.get("last_name", "")
        user.email = self.cleaned_data.get("email")
        if commit:
            user.save()
        return user


class GameForm(forms.ModelForm):
    class Meta:
        model = Game
        # Įtraukiame visus laukus, kuriuos adminas galės redaguoti
        fields = [
            'name',
            'submission_start_date', 'submission_end_date',
            'voting_start_date', 'voting_end_date' # <<< Pridėti balsavimo laukai
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-gray-100',
                'placeholder': 'Pvz., 90-ųjų hitai, Eurovizija 2024...'
            }),
            # Naudojame HTML5 datetime-local tipą patogiam pasirinkimui
            'submission_start_date': forms.DateTimeInput(
                attrs={
                    'type': 'datetime-local',
                    'class': 'mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-gray-100'
                },
                format='%Y-%m-%dT%H:%M' # Formatas reikalingas DateTimeInput
            ),
            'submission_end_date': forms.DateTimeInput(
                 attrs={
                    'type': 'datetime-local',
                    'class': 'mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-gray-100'
                },
                format='%Y-%m-%dT%H:%M'
            ),
             # <<< Pridėti widget'ai balsavimo datoms >>>
            'voting_start_date': forms.DateTimeInput(
                 attrs={
                    'type': 'datetime-local',
                    'class': 'mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-gray-100'
                },
                format='%Y-%m-%dT%H:%M'
            ),
            'voting_end_date': forms.DateTimeInput(
                 attrs={
                    'type': 'datetime-local',
                    'class': 'mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-gray-100'
                },
                format='%Y-%m-%dT%H:%M'
            ),
        }
        labels = {
            'name': 'Žaidimo tema / pavadinimas',
            'submission_start_date': 'Dainų kėlimo pradžia',
            'submission_end_date': 'Dainų kėlimo pabaiga',
            'voting_start_date': 'Balsavimo pradžia', # <<< Pridėta etiketė
            'voting_end_date': 'Balsavimo pabaiga',    # <<< Pridėta etiketė
        }
        # Galima pridėti help_text laukams
        help_texts = {
             'submission_start_date': 'Nuo kada galima kelti dainas.',
             'submission_end_date': 'Iki kada galima kelti dainas.',
             'voting_start_date': 'Nuo kada galima balsuoti (gali būti palikta tuščia, jei bus skelbiama rankiniu būdu).',
             'voting_end_date': 'Iki kada galima balsuoti (privaloma nustatyti ateities datą, jei norima skelbti balsavimą).',
        }

    # Papildoma validacija datų sekai
    def clean(self):
        cleaned_data = super().clean()
        sub_start = cleaned_data.get("submission_start_date")
        sub_end = cleaned_data.get("submission_end_date")
        vote_start = cleaned_data.get("voting_start_date")
        vote_end = cleaned_data.get("voting_end_date")

        # 1. Kėlimo pabaiga po kėlimo pradžios
        if sub_start and sub_end and sub_end <= sub_start:
            self.add_error('submission_end_date', "Kėlimo pabaiga turi būti vėlesnė nei pradžia.")

        # 2. Balsavimo pabaiga po balsavimo pradžios (jei balsavimo pradžia nustatyta)
        if vote_start and vote_end and vote_end <= vote_start:
             self.add_error('voting_end_date', "Balsavimo pabaiga turi būti vėlesnė nei pradžia.")

        # 3. Balsavimo pradžia po kėlimo pabaigos (jei abi nustatytos)
        if sub_end and vote_start and vote_start < sub_end:
             self.add_error('voting_start_date', "Balsavimo pradžia negali būti ankstesnė už dainų kėlimo pabaigą.")

        # 4. Patikrinam, ar balsavimo pabaiga yra ateityje (jei ji nustatyta)
        # Šitą logiką gal labiau tiktų tikrinti view'e prieš skelbiant balsavimą,
        # bet galima pridėti ir čia kaip papildomą patikrą redaguojant.
        # from django.utils import timezone
        # if vote_end and vote_end <= timezone.now():
        #      self.add_error('voting_end_date', "Balsavimo pabaigos data turi būti ateityje.")

        return cleaned_data


    # Galima pridėti validaciją, pvz., kad pabaigos data būtų vėlesnė už pradžios
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("submission_start_date")
        end_date = cleaned_data.get("submission_end_date")

        if start_date and end_date:
            if end_date <= start_date:
                self.add_error('submission_end_date', "Kėlimo pabaigos data turi būti vėlesnė nei pradžios data.")

        return cleaned_data

class SongForm(forms.ModelForm):
    class Meta:
        model = Song
        # Nurodome laukus, kuriuos pildys vartotojas
        fields = ['title', 'youtube_url']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-gray-100',
                'placeholder': 'Įveskite dainos pavadinimą'
            }),
            'youtube_url': forms.URLInput(attrs={
                 'class': 'mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-gray-100',
                 'placeholder': 'Nukopijuokite pilną YouTube nuorodą čia (pvz., https://www.youtube.com/watch?v=...)'
            }),
        }
        labels = {
            'title': 'Dainos pavadinimas',
            'youtube_url': 'YouTube nuoroda',
        }

    # Papildoma validacija YouTube nuorodai (paprastas pavyzdys)
    def clean_youtube_url(self):
        url = self.cleaned_data.get('youtube_url')
        if url:
            # Labai paprastas tikrinimas, galima daryti sudėtingesnį su regex
            if not ('youtube.com/watch' in url or 'youtu.be/' in url):
                raise forms.ValidationError("Prašome įvesti teisingą YouTube vaizdo įrašo nuorodą.")
        return url

class UserProfileEditForm(forms.ModelForm):
    username = forms.CharField(
        label="Prisijungimo vardas",
        max_length=150,
        required=True,
        help_text='Privalomas. 150 simbolių ar mažiau. Leidžiamos tik raidės, skaičiai ir @/./+/-/_ ženklai.',
        widget=forms.TextInput(attrs={'autocomplete': 'username', 'class': 'mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-gray-100'})
    )
    email = forms.EmailField(
        label="El. pašto adresas",
        required=True,
        widget=forms.EmailInput(attrs={'autocomplete': 'email', 'class': 'mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-gray-100'})
    )
    first_name = forms.CharField(
        label="Vardas",
        max_length=150, required=False,
        widget=forms.TextInput(attrs={'autocomplete': 'given-name', 'class': 'mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-gray-100'})
    )
    last_name = forms.CharField(
        label="Pavardė",
        max_length=150, required=False,
        widget=forms.TextInput(attrs={'autocomplete': 'family-name', 'class': 'mt-1 block w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-300 dark:border-gray-600 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm text-gray-900 dark:text-gray-100'})
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'first_name', 'last_name'] # <-- Pridėtas 'username'

    def clean_username(self):
        """ Tikrina, ar pakeistas vartotojo vardas nėra užimtas kito vartotojo. """
        username = self.cleaned_data.get('username')
        # self.instance yra redaguojamas User objektas
        # Tikrinam tik tuo atveju, jei username buvo pakeistas
        if username != self.instance.username:
            # Ieškom, ar egzistuoja kitas vartotojas su tokiu username
            if User.objects.filter(username=username).exclude(pk=self.instance.pk).exists():
                raise forms.ValidationError("Vartotojas su tokiu prisijungimo vardu jau egzistuoja.")
        return username




