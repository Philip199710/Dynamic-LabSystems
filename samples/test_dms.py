from labs.testing import default_lab
import json

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase, override_settings
from django.urls import reverse

from catalog.models import FuelType, SpecLimit, TestMethod
from labtests.models import SampleTest, TestResult
from reports.models import Certificate
from samples.models import Sample

User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DMS_NOTIFICATION_EMAIL="dms@dynamicapac.com",
    DMS_EMAIL_ASYNC=False,
    SAMPLE_NOTIFICATION_EMAIL="",
)
class DmsFeedTests(TestCase):
    def setUp(self):
        self.fuel = FuelType.objects.get_or_create(code="DIESEL", defaults={"name": "Diesel"})[0]
        self.method = TestMethod.objects.create(
            code="CETANE-D613", name="Cetane Number", standard_reference="ASTM D613", unit="—"
        )
        SpecLimit.objects.create(test_method=self.method, fuel_type=self.fuel, min_value=51, max_value=None)
        self.boss = User.objects.create_superuser("boss", password="x")

    def _dms(self, event):
        return [m for m in mail.outbox if m.extra_headers.get("X-Dynamic-Event") == event]

    def _payload(self, message):
        name, content, _ = next(a for a in message.attachments if a[0] == "event.json")
        return json.loads(content)

    def test_registering_a_sample_emails_dms(self):
        self.client.force_login(self.boss)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(
                reverse("samples:create"),
                {"fuel_type": self.fuel.pk, "source": "Juba depot", "source_type": "TANK",
                 "date_received": "2026-10-19"},
            )
        sample = Sample.objects.get()
        sent = self._dms("sample.registered")
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0].to, ["dms@dynamicapac.com"])
        self.assertIn(sample.sample_id, sent[0].subject)
        self.assertEqual(self._payload(sent[0])["sample"]["sample_id"], sample.sample_id)

    def test_completing_all_tests_emails_dms_once(self):
        sample = Sample.objects.create(fuel_type=self.fuel, source="A", lab=default_lab())
        st = SampleTest.objects.create(sample=sample, test_method=self.method)
        with self.captureOnCommitCallbacks(execute=True):
            TestResult(sample_test=st, value=58.0, entered_by=self.boss).record(self.boss)
        sent = self._dms("sample.tested")
        self.assertEqual(len(sent), 1)
        payload = self._payload(sent[0])
        self.assertEqual(payload["results"][0]["value"], 58.0)
        # Amending a result on an already-complete sample doesn't resend.
        with self.captureOnCommitCallbacks(execute=True):
            result = st.testresult
            result.value = 59.0
            result.record(self.boss)
        self.assertEqual(len(self._dms("sample.tested")), 1)

    def test_issuing_a_certificate_emails_dms_with_pdf(self):
        sample = Sample.objects.create(fuel_type=self.fuel, source="A", lab=default_lab())
        st = SampleTest.objects.create(sample=sample, test_method=self.method)
        TestResult(sample_test=st, value=58.0, entered_by=self.boss).record(self.boss)
        mail.outbox.clear()
        self.client.force_login(self.boss)
        with self.captureOnCommitCallbacks(execute=True):
            self.client.post(reverse("reports:issue_certificate", args=[sample.pk]))
        cert = Certificate.objects.get(sample=sample)
        sent = self._dms("certificate.issued")
        self.assertEqual(len(sent), 1)
        self.assertIn(cert.certificate_number, sent[0].subject)
        names = [a[0] for a in sent[0].attachments]
        self.assertTrue(any(n.endswith(".pdf") for n in names))

    @override_settings(EMAIL_BACKEND="dynamiclab.no_such_backend.EmailBackend")
    def test_mail_failure_never_breaks_registration(self):
        self.client.force_login(self.boss)
        with self.captureOnCommitCallbacks(execute=True):
            resp = self.client.post(
                reverse("samples:create"),
                {"fuel_type": self.fuel.pk, "source": "Juba depot", "source_type": "TANK",
                 "date_received": "2026-10-19"},
            )
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(Sample.objects.count(), 1)
