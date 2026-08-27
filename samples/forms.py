from django import forms

from .models import Sample


class SampleForm(forms.ModelForm):
    class Meta:
        model = Sample
        fields = ["fuel_type", "source", "client", "date_received", "storage_location", "notes"]
        widgets = {
            "date_received": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
        labels = {"client": "Client portal account (optional)"}
        help_texts = {
            "client": "Link this sample to a client-portal account so they can see its status and download the certificate once complete.",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["client"].required = False
        self.fields["client"].empty_label = "— not linked to a portal account —"
