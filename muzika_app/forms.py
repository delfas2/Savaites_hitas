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
            'name': forms.TextInput(attrs={'class': 'mt-1 block w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 placeholder-gray-500'}),
            'information': forms.Textarea(attrs={'rows': 3, 'class': 'mt-1 block w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 placeholder-gray-500'}),
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
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class': 'mt-1 block w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 placeholder-gray-500'}),
        help_text="",
    )
    password2 = forms.CharField(
        label="Pakartokite slaptažodį",
        strip=False,
        widget=forms.PasswordInput(attrs={'autocomplete': 'new-password', 'class': 'mt-1 block w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 placeholder-gray-500'}),
        help_text="Įveskite tą patį slaptažodį kaip ir pirmą kartą, patikrinimui.",
    )
    email = forms.EmailField(
        label="El. pašto adresas",
        max_length=254, required=True,
        widget=forms.EmailInput(attrs={'autocomplete': 'email', 'class': 'mt-1 block w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 placeholder-gray-500'})
    )
    first_name = forms.CharField(
        label="Vardas",
        max_length=150, required=False,
        widget=forms.TextInput(attrs={'autocomplete': 'given-name', 'class': 'mt-1 block w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 placeholder-gray-500'})
        )
    last_name = forms.CharField(
        label="Pavardė",
        max_length=150, required=False,
        widget=forms.TextInput(attrs={'autocomplete': 'family-name', 'class': 'mt-1 block w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 placeholder-gray-500'})
        )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ("username", "email", "first_name", "last_name")
        field_classes = {"username": UsernameField}
        widgets = {
             'username': forms.TextInput(attrs={'autocomplete': 'username', 'class': 'mt-1 block w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 placeholder-gray-500'}),
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
        model = Game        # 'voting_start_date' nebėra atskiras laukas – jis automatiškai
        # prilyginamas dainų kėlimo pabaigos laikui (submission_end_date).
        fields = [
            'name', 'description',
            'submission_start_date', 'submission_end_date',
            'voting_end_date'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'mt-1 block w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 placeholder-gray-500',
                'placeholder': 'Pvz., 90-ųjų hitai, Eurovizija 2024...'
            }),
            'description': forms.Textarea(attrs={
                'rows': 3,
                'class': 'mt-1 block w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 placeholder-gray-500',
                'placeholder': 'Trumpai aprašykite žaidimo taisykles ar temą (matysis banerio viršuje po pavadinimu)...'
            }),
            'submission_start_date': forms.DateTimeInput(
                attrs={
                    'type': 'datetime-local',
                    'lang': 'lt-LT',
                    'step': '60',
                    'class': 'mt-1 block w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 placeholder-gray-500'
                },
                format='%Y-%m-%dT%H:%M' # Formatas reikalingas DateTimeInput
            ),
            'submission_end_date': forms.DateTimeInput(
                 attrs={
                    'type': 'datetime-local',
                    'lang': 'lt-LT',
                    'step': '60',
                    'class': 'mt-1 block w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 placeholder-gray-500'
                },
                format='%Y-%m-%dT%H:%M'
            ),
            'voting_end_date': forms.DateTimeInput(
                 attrs={
                    'type': 'datetime-local',
                    'lang': 'lt-LT',
                    'step': '60',
                    'class': 'mt-1 block w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 placeholder-gray-500'
                },
                format='%Y-%m-%dT%H:%M'            ),
        }
        labels = {
            'name': 'Žaidimo tema / pavadinimas',
            'description': 'Žaidimo aprašymas (nebūtina)',
            'submission_start_date': 'Dainų kėlimo pradžia',
            'submission_end_date': 'Dainų kėlimo pabaiga (= balsavimo pradžia)',
            'voting_end_date': 'Balsavimo pabaiga',
        }
        help_texts = {
             'submission_start_date': 'Nuo kada galima kelti dainas.',
             'submission_end_date': 'Iki kada galima kelti dainas. Balsavimas prasidės iškart po šio laiko.',
             'voting_end_date': 'Iki kada galima balsuoti (privaloma nustatyti ateities datą).',
        }

    def clean(self):
        cleaned_data = super().clean()
        sub_start = cleaned_data.get("submission_start_date")
        sub_end = cleaned_data.get("submission_end_date")
        vote_end = cleaned_data.get("voting_end_date")

        # 1. Kėlimo pabaiga po kėlimo pradžios
        if sub_start and sub_end and sub_end <= sub_start:
            self.add_error('submission_end_date', "Kėlimo pabaiga turi būti vėlesnė nei pradžia.")

        # 2. Balsavimo pradžia = dainų kėlimo pabaiga
        if sub_end:
            cleaned_data['voting_start_date'] = sub_end

        # 3. Balsavimo pabaiga po balsavimo pradžios (t.y. po kėlimo pabaigos)
        if sub_end and vote_end and vote_end <= sub_end:
            self.add_error('voting_end_date', "Balsavimo pabaiga turi būti vėlesnė nei dainų kėlimo pabaiga.")

        return cleaned_data

    def save(self, commit=True):
        game = super().save(commit=False)
        # Automatiškai prilyginam balsavimo pradžią kėlimo pabaigai
        if game.submission_end_date:
            game.voting_start_date = game.submission_end_date
        if commit:
            game.save()
        return game


class SongForm(forms.ModelForm):
    class Meta:
        model = Song
        # Nurodome laukus, kuriuos pildys vartotojas
        fields = ['title', 'youtube_url']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'mt-1 block w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 placeholder-gray-500',
                'placeholder': 'Įveskite dainos pavadinimą'
            }),
            'youtube_url': forms.URLInput(attrs={
                 'class': 'mt-1 block w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 placeholder-gray-500',
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
        widget=forms.TextInput(attrs={'autocomplete': 'username', 'class': 'mt-1 block w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 placeholder-gray-500'})
    )
    email = forms.EmailField(
        label="El. pašto adresas",
        required=True,
        widget=forms.EmailInput(attrs={'autocomplete': 'email', 'class': 'mt-1 block w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 placeholder-gray-500'})
    )
    first_name = forms.CharField(
        label="Vardas",
        max_length=150, required=False,
        widget=forms.TextInput(attrs={'autocomplete': 'given-name', 'class': 'mt-1 block w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 placeholder-gray-500'})
    )
    last_name = forms.CharField(
        label="Pavardė",
        max_length=150, required=False,
        widget=forms.TextInput(attrs={'autocomplete': 'family-name', 'class': 'mt-1 block w-full bg-gray-900 border border-gray-800 rounded-xl px-4 py-2.5 text-xs text-white focus:outline-none focus:border-brand-500 placeholder-gray-500'})
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




