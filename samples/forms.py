from django import forms

from .models import Sample


class SampleForm(forms.ModelForm):
    class Meta:
        model = Sample
        fields = ["fuel_type", "source", "date_received", "storage_location", "notes"]
        widgets = {
            "date_received": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 3}),
        }
