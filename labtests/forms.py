from django import forms

from catalog.models import Instrument

from .models import SampleTest, TestResult


class AssignTestForm(forms.ModelForm):
    class Meta:
        model = SampleTest
        fields = ["test_method", "assigned_to", "due_date"]
        widgets = {"due_date": forms.DateInput(attrs={"type": "date"})}

    def __init__(self, *args, sample=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._sample = sample
        if sample is not None:
            existing = sample.tests.values_list("test_method_id", flat=True)
            # Restrict to methods with a spec limit on file for this sample's
            # fuel type, so e.g. Research Octane Number never shows up as
            # assignable on a diesel sample.
            self.fields["test_method"].queryset = (
                self.fields["test_method"]
                .queryset.filter(active=True, spec_limits__fuel_type=sample.fuel_type)
                .exclude(id__in=existing)
                .distinct()
            )

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self._sample is not None:
            instance.sample = self._sample
        if commit:
            instance.save()
        return instance


class ResultEntryForm(forms.ModelForm):
    class Meta:
        model = TestResult
        fields = ["value", "instrument", "replicate_values", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # No strict test-method-to-instrument mapping exists in the catalog
        # (instrument_type is a free-text hint, not a formal link), so this
        # offers every active instrument rather than guessing a match —
        # the analyst picks the one they actually used. Out-of-service
        # instruments are excluded since a result shouldn't be attributed
        # to equipment that's flagged as unusable.
        field = self.fields["instrument"]
        field.queryset = Instrument.objects.filter(status=Instrument.STATUS_ACTIVE).order_by("name")
        field.required = False
        field.empty_label = "— not recorded —"
        field.label_from_instance = lambda i: f"{i.name} ({i.instrument_type})" if i.instrument_type else i.name
