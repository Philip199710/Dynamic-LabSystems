from django import forms

from .models import Sample


class SampleForm(forms.ModelForm):
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
            "client",
            "date_received",
            "storage_location",
            "notes",
        ]
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
        for name in ("source_type", "tank_or_tanker_id", "tanker_plate_number", "origin", "destination_port"):
            self.fields[name].required = False

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("source_type") == Sample.SOURCE_TYPE_ROAD_TANKER and not cleaned.get("tanker_plate_number"):
            self.add_error("tanker_plate_number", "Required when the sample is drawn from a road tanker.")
        return cleaned
