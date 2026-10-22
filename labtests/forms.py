from django import forms

from catalog.models import Instrument

from .models import SampleTest, TestResult


def assignable_methods(fuel_type):
    from catalog.models import TestMethod

    # Only tests the lab can actually run: methods linked to an active
    # instrument. Falls back to the spec-limit rule if no instruments are
    # registered (e.g. a fresh install).
    lab = TestMethod.objects.filter(active=True, instruments__status=Instrument.STATUS_ACTIVE)
    if not lab.exists():
        lab = TestMethod.objects.filter(active=True, spec_limits__fuel_type=fuel_type)
    return lab.distinct().order_by("name")


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
            # Offer the tests the lab's instruments run. Where the product
            # spec has no limit for a test, the result is reported without a
            # pass/fail verdict — the label says so.
            fuel = sample.fuel_type
            field = self.fields["test_method"]
            field.queryset = assignable_methods(fuel).exclude(id__in=existing)
            limits = {
                sl.test_method_id: sl.range_display()
                for sl in fuel.spec_limits.all()
                if sl.min_value is not None or sl.max_value is not None
            }
            instruments = {}
            for inst in Instrument.objects.filter(status=Instrument.STATUS_ACTIVE).prefetch_related("test_methods"):
                for tm in inst.test_methods.all():
                    instruments.setdefault(tm.id, []).append(inst.name)

            def label(m):
                text = f"{m.name} · {m.standard_reference}"
                if m.id in instruments:
                    text += f" · {', '.join(instruments[m.id])}"
                return text + (f" — spec {limits[m.id]} {m.unit}" if m.id in limits else " — report only")

            field.label_from_instance = label

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

    def __init__(self, *args, sample_test=None, **kwargs):
        super().__init__(*args, **kwargs)
        # No strict test-method-to-instrument mapping exists in the catalog
        # (instrument_type is a free-text hint, not a formal link), so this
        # offers every active instrument rather than guessing a match —
        # the analyst picks the one they actually used. Out-of-service
        # instruments are excluded since a result shouldn't be attributed
        # to equipment that's flagged as unusable.
        field = self.fields["instrument"]
        active = Instrument.objects.filter(status=Instrument.STATUS_ACTIVE).order_by("name")
        # Offer the instruments registered for this test's ASTM method first;
        # fall back to every active instrument if none are linked yet.
        if sample_test is None and self.instance.sample_test_id:
            sample_test = self.instance.sample_test
        linked = active.filter(test_methods=sample_test.test_method_id) if sample_test else active.none()
        field.queryset = linked if linked.exists() else active
        if linked.count() == 1 and not self.instance.pk and not self.is_bound:
            self.initial.setdefault("instrument", linked.first().pk)
        field.required = False
        field.empty_label = "— not recorded —"
        field.label_from_instance = lambda i: f"{i.name} ({i.instrument_type})" if i.instrument_type else i.name
