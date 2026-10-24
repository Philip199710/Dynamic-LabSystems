from labs.testing import default_lab, login_lab_user, make_lab_user
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from catalog.models import FuelType
from samples.models import Sample

from .models import Channel, Message

User = get_user_model()


class ChatTests(TestCase):
    def setUp(self):
        self.a = make_lab_user("analyst1", first_name="Mia", last_name="Torres")
        self.b = make_lab_user("qa1", first_name="Owen", last_name="Silva")
        self.general = Channel.objects.get(name="general", lab=default_lab())  # created by the data migration

    def test_default_channels_exist(self):
        self.assertTrue(Channel.objects.filter(name__in=["general", "sample-intake", "results-qa"]).count() == 3)

    def test_login_required(self):
        resp = self.client.get(reverse("chat:home"))
        self.assertEqual(resp.status_code, 302)
        self.assertIn("/login/", resp["Location"])

    def test_send_and_poll(self):
        login_lab_user(self.client, self.a)
        resp = self.client.post(reverse("chat:send", args=[self.general.pk]), {"body": "Tanker 7 arrived"})
        self.assertEqual(resp.status_code, 201)
        self.assertEqual(resp.json()["message"]["author"], "Mia Torres")
        login_lab_user(self.client, self.b)
        data = self.client.get(reverse("chat:messages", args=[self.general.pk]), {"after": 0}).json()
        self.assertEqual([m["html"] for m in data["messages"]], ["Tanker 7 arrived"])
        self.assertFalse(data["messages"][0]["mine"])

    def test_empty_message_rejected(self):
        login_lab_user(self.client, self.a)
        resp = self.client.post(reverse("chat:send", args=[self.general.pk]), {"body": "   "})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(Message.objects.count(), 0)

    def test_html_is_escaped_and_sample_ids_link(self):
        fuel = FuelType.objects.get_or_create(code="DIESEL", defaults={"name": "Diesel"})[0]
        sample = Sample.objects.create(fuel_type=fuel, source="A", lab=default_lab())
        login_lab_user(self.client, self.a)
        body = f"<script>x</script> see {sample.sample_id}"
        html = self.client.post(reverse("chat:send", args=[self.general.pk]), {"body": body}).json()["message"]["html"]
        self.assertNotIn("<script>", html)
        self.assertIn(reverse("samples:detail", args=[sample.pk]), html)

    def test_unread_counts(self):
        Message.objects.create(channel=self.general, author=self.a, body="one")
        Message.objects.create(channel=self.general, author=self.a, body="two")
        login_lab_user(self.client, self.b)
        self.assertEqual(self.client.get(reverse("chat:unread")).json()["unread"], 2)
        self.client.get(reverse("chat:channel", args=[self.general.pk]))
        self.assertEqual(self.client.get(reverse("chat:unread")).json()["unread"], 0)
        # Your own messages never count as unread.
        login_lab_user(self.client, self.a)
        self.assertEqual(self.client.get(reverse("chat:unread")).json()["unread"], 0)

    def test_create_channel(self):
        login_lab_user(self.client, self.a)
        self.client.post(reverse("chat:create_channel"), {"name": "Night Shift"})
        self.assertTrue(Channel.objects.filter(name="night-shift").exists())

    def test_messages_cannot_be_deleted(self):
        msg = Message.objects.create(channel=self.general, author=self.a, body="kept")
        from django.db.models import ProtectedError

        with self.assertRaises(ProtectedError):
            self.general.delete()
        self.assertTrue(Message.objects.filter(pk=msg.pk).exists())
