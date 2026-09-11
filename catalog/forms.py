from django import forms

from .models import CalibrationRecord


class CalibrationRecordForm(forms.ModelForm):
    class Meta:
        model = CalibrationRecord
        fields = ["performed_at", "next_due_date", "certificate_reference", "notes"]
        widgets = {
            "performed_at": forms.DateInput(attrs={"type": "date"}),
            "next_due_date": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 2}),
        }
