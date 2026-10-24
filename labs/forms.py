from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password

from accounts.roles import DYNAMIC_ADMIN_GROUP

from .models import Lab


class LabForm(forms.ModelForm):
    class Meta:
        model = Lab
        fields = ["name", "code", "location", "country", "contact_email", "max_logins", "devices_per_login",
                  "auto_approve_first_device", "licence_expires", "is_active", "notes"]
        widgets = {"licence_expires": forms.DateInput(attrs={"type": "date"}), "notes": forms.Textarea(attrs={"rows": 2})}
        labels = {"max_logins": "Licensed logins", "devices_per_login": "PCs per login", "is_active": "Licence active"}


class NewLabForm(LabForm):
    copy_instruments_from = forms.ModelChoiceField(
        queryset=Lab.objects.all(), required=False, empty_label="— start with no instruments —",
        label="Copy instrument list from",
    )

    class Meta(LabForm.Meta):
        fields = ["name", "code", "location", "country", "contact_email", "max_logins", "devices_per_login", "licence_expires"]


class LabUserForm(forms.Form):
    username = forms.CharField(max_length=150)
    full_name = forms.CharField(max_length=150)
    email = forms.EmailField(required=False)
    role = forms.ModelChoiceField(queryset=Group.objects.none(), required=False, empty_label="— no role —")
    password = forms.CharField(widget=forms.PasswordInput, help_text="Give this to the user; they can change it later.")

    def __init__(self, *args, lab=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.lab = lab
        self.fields["role"].queryset = Group.objects.exclude(name=DYNAMIC_ADMIN_GROUP).order_by("name")

    def clean_username(self):
        username = self.cleaned_data["username"].strip()
        if get_user_model().objects.filter(username__iexact=username).exists():
            raise forms.ValidationError("That username is already taken.")
        return username

    def clean_password(self):
        password = self.cleaned_data["password"]
        validate_password(password)
        return password

    def clean(self):
        cleaned = super().clean()
        if self.lab is not None and self.lab.seats_left() <= 0:
            raise forms.ValidationError(
                f"{self.lab.name} has used all {self.lab.max_logins} licensed logins. "
                "Raise the licence or deactivate a login first."
            )
        return cleaned
