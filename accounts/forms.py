from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password

from samples.models import Sample

from .models import Client, ClientProfile

User = get_user_model()


class ClientRegistrationForm(forms.Form):
    """Self-service signup for a client-portal account.

    Creates the User + Client (get-or-create by name) + ClientProfile as a
    unit, with the profile left unapproved — see ClientProfile docstring.
    """

    company_name = forms.CharField(
        max_length=150,
        label="Company / organization name",
        help_text="If your company already has a portal, use the exact same name — a Lab Manager will link your account to it.",
    )
    full_name = forms.CharField(max_length=150, label="Your name")
    email = forms.EmailField(label="Work email", help_text="This will be your username.")
    password1 = forms.CharField(label="Password", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Confirm password", widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(username__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean_password1(self):
        password1 = self.cleaned_data.get("password1", "")
        validate_password(password1)
        return password1

    def clean(self):
        cleaned = super().clean()
        p1, p2 = cleaned.get("password1"), cleaned.get("password2")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Passwords don't match.")
        return cleaned

    def save(self):
        email = self.cleaned_data["email"]
        full_name = self.cleaned_data["full_name"].strip()
        first_name, _, last_name = full_name.partition(" ")

        user = User(username=email, email=email, first_name=first_name, last_name=last_name)
        user.set_password(self.cleaned_data["password1"])
        user.save()

        client, _ = Client.objects.get_or_create(name=self.cleaned_data["company_name"].strip())
        profile = ClientProfile.objects.create(user=user, client=client)
        return profile


class ClientSampleRequestForm(forms.ModelForm):
    """A client submitting a sample for testing, from the client portal.

    Deliberately narrow: no status, client, or received_by fields — the view
    sets those. The sample lands as Sample.STATUS_REQUESTED, invisible to
    testing workflows until a staff member confirms physical intake (see
    samples.views.sample_confirm_intake).
    """

    class Meta:
        model = Sample
        fields = [
            "fuel_type",
            "source",
            "source_type",
            "tank_or_tanker_id",
            "tanker_plate_number",
            "origin",
            "destination_port",
            "notes",
        ]
        widgets = {"notes": forms.Textarea(attrs={"rows": 3})}
        labels = {"source": "Source / description", "notes": "Notes for the lab (optional)"}
        help_texts = {
            "source": "e.g. the storage tank, delivery, or site this sample was drawn from.",
            "notes": "Quantity shipped, urgency, special handling — anything the lab should know.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ("source_type", "tank_or_tanker_id", "tanker_plate_number", "origin", "destination_port"):
            self.fields[name].required = False

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("source_type") == Sample.SOURCE_TYPE_ROAD_TANKER and not cleaned.get("tanker_plate_number"):
            self.add_error("tanker_plate_number", "Required when the sample is drawn from a road tanker.")
        return cleaned
