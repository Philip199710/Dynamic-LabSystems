from django import forms

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
        fields = ["value", "replicate_values", "notes"]
        widgets = {"notes": forms.Textarea(attrs={"rows": 2})}
