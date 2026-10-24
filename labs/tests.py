from django.contrib.auth import get_user_model
from django.core import mail
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from catalog.models import FuelType
from chat.models import Channel
from samples.models import Sample

from .devices import DEVICE_COOKIE
from .models import Device, Lab, LabMember, LoginEvent
from .testing import default_lab, login_lab_user, make_lab_user

User = get_user_model()
PW = "Lab-pass-2026!"


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DMS_NOTIFICATION_EMAIL="dms@dynamicapac.com", DMS_EMAIL_ASYNC=False, GEOIP_LOOKUP=False,
)
class DeviceApprovalTests(TestCase):
    def setUp(self):
        self.lab = default_lab()
        self.user = make_lab_user("analyst9", password=PW)

    def sign_in(self, client, ip="196.1.1.10"):
        with self.captureOnCommitCallbacks(execute=True):
            return client.post(reverse("login"), {"username": "analyst9", "password": PW}, REMOTE_ADDR=ip)

    def test_first_pc_is_approved_and_second_pc_waits(self):
        pc1, pc2 = Client(), Client()
        self.assertEqual(self.sign_in(pc1).status_code, 302)
        self.assertIn(DEVICE_COOKIE, pc1.cookies)
        self.assertEqual(self.user.devices.get().status, Device.STATUS_APPROVED)

        resp = self.sign_in(pc2)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "waiting for approval")
        self.assertEqual(pc2.get(reverse("dashboard:home")).status_code, 302)  # not signed in
        self.assertEqual(self.user.devices.filter(status=Device.STATUS_PENDING).count(), 1)
        self.assertTrue(any("New PC waiting for approval" in m.subject for m in mail.outbox))
        self.assertTrue(LoginEvent.objects.filter(user=self.user, outcome=LoginEvent.OUTCOME_PENDING).exists())

    def test_approving_second_pc_needs_old_one_revoked(self):
        pc1, pc2 = Client(), Client()
        self.sign_in(pc1)
        self.sign_in(pc2)
        boss = User.objects.create_superuser("boss", password=PW)
        admin = Client()
        admin.force_login(boss)
        pending = self.user.devices.get(status=Device.STATUS_PENDING)
        admin.post(reverse("labs:device_decide", args=[pending.pk, "approve"]))
        pending.refresh_from_db()
        self.assertEqual(pending.status, Device.STATUS_PENDING)  # licence is 1 PC per login
        old = self.user.devices.get(status=Device.STATUS_APPROVED)
        admin.post(reverse("labs:device_decide", args=[old.pk, "revoke"]))
        admin.post(reverse("labs:device_decide", args=[pending.pk, "approve"]))
        pending.refresh_from_db()
        self.assertEqual(pending.status, Device.STATUS_APPROVED)
        # PC 1 is signed out on its next page; PC 2 can now sign in.
        self.assertEqual(pc1.get(reverse("dashboard:home")).status_code, 302)
        self.assertEqual(self.sign_in(pc2).status_code, 302)
        self.assertEqual(pc2.get(reverse("dashboard:home")).status_code, 200)

    def test_new_network_is_flagged_and_emailed(self):
        pc = Client()
        self.sign_in(pc, ip="196.1.1.10")
        pc.post(reverse("logout"))
        mail.outbox.clear()
        self.sign_in(pc, ip="41.77.5.20")
        event = LoginEvent.objects.filter(user=self.user, outcome=LoginEvent.OUTCOME_OK).first()
        self.assertTrue(event.new_network)
        self.assertTrue(any("new network" in m.subject for m in mail.outbox))

    def test_suspended_lab_cannot_sign_in(self):
        Lab.objects.filter(pk=self.lab.pk).update(is_active=False)
        resp = self.sign_in(Client())
        self.assertContains(resp, "licence is not active")

    def test_licensed_login_limit(self):
        Lab.objects.filter(pk=self.lab.pk).update(max_logins=LabMember.objects.filter(lab=self.lab).count())
        boss = User.objects.create_superuser("boss", password=PW)
        admin = Client()
        admin.force_login(boss)
        resp = admin.post(reverse("labs:detail", args=[self.lab.pk]), {
            "add_user": "1", "user-username": "extra", "user-full_name": "Extra Person", "user-password": PW,
        })
        self.assertContains(resp, "used all")
        self.assertFalse(User.objects.filter(username="extra").exists())


class LabIsolationTests(TestCase):
    def setUp(self):
        self.fuel = FuelType.objects.get_or_create(code="DIESEL", defaults={"name": "Diesel"})[0]
        self.lab_a = default_lab()
        self.lab_b = Lab.objects.create(name="Other Lab", code="OTH-01")
        Channel.objects.create(lab=self.lab_b, name="general")
        self.a_user = make_lab_user("alice", lab=self.lab_a)
        self.b_user = make_lab_user("bob", lab=self.lab_b)
        self.a_sample = Sample.objects.create(fuel_type=self.fuel, source="A", lab=self.lab_a)
        self.b_sample = Sample.objects.create(fuel_type=self.fuel, source="B", lab=self.lab_b)

    def test_each_lab_sees_only_its_own_samples(self):
        login_lab_user(self.client, self.b_user)
        self.assertEqual(self.client.get(reverse("samples:detail", args=[self.a_sample.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("samples:detail", args=[self.b_sample.pk])).status_code, 200)
        listing = self.client.get(reverse("samples:list")).content.decode()
        self.assertIn(self.b_sample.sample_id, listing)
        self.assertNotIn(self.a_sample.sample_id, listing)
        self.assertEqual(self.client.get(reverse("reports:coa_pdf", args=[self.a_sample.pk])).status_code, 404)

    def test_new_sample_belongs_to_the_registering_lab(self):
        login_lab_user(self.client, self.b_user)
        self.client.post(reverse("samples:create"), {"fuel_type": self.fuel.pk, "source": "Port", "source_type": "TANK",
                                                     "date_received": "2026-10-24"})
        self.assertEqual(Sample.objects.filter(source="Port").get().lab, self.lab_b)

    def test_chat_is_separate(self):
        a_general = Channel.objects.get(lab=self.lab_a, name="general")
        login_lab_user(self.client, self.b_user)
        self.assertEqual(self.client.get(reverse("chat:channel", args=[a_general.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("chat:send", args=[a_general.pk]), {"body": "hi"}).status_code, 404)
