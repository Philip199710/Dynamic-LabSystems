from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

User = get_user_model()


class SeparateLoginTests(TestCase):
    def setUp(self):
        from django.contrib.auth.models import Group

        self.lab = User.objects.create_user("labmanager", password="pw-12345", is_staff=True)
        self.boss = User.objects.create_superuser("phil", password="pw-12345")
        self.dyn = User.objects.create_user("ops", password="pw-12345", is_staff=True)
        self.dyn.groups.add(Group.objects.get(name="Dynamic Admin"))

    def test_lab_login_accepts_lab_staff(self):
        resp = self.client.post(reverse("login"), {"username": "labmanager", "password": "pw-12345"})
        self.assertEqual(resp.status_code, 302)

    def test_lab_login_refuses_dynamic_admins(self):
        for name in ("phil", "ops"):
            resp = self.client.post(reverse("login"), {"username": name, "password": "pw-12345"})
            self.assertEqual(resp.status_code, 200)
            self.assertContains(resp, "admin sign-in")

    def test_admin_login_refuses_lab_staff(self):
        resp = self.client.post(reverse("dynamic_login"), {"username": "labmanager", "password": "pw-12345"})
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Dynamic APAC administrators only")

    def test_admin_login_lands_on_console(self):
        resp = self.client.post(reverse("dynamic_login"), {"username": "ops", "password": "pw-12345"})
        self.assertRedirects(resp, reverse("dynamic_console"))
        self.assertContains(self.client.get(reverse("dynamic_console")), "Admin console")

    def test_console_and_django_admin_closed_to_lab_staff(self):
        self.client.force_login(self.lab)
        self.assertEqual(self.client.get(reverse("dynamic_console")).status_code, 403)
        self.assertNotEqual(self.client.get("/admin/").status_code, 200)
        self.client.force_login(self.boss)
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_admin_login_url_redirects_to_dynamic_login(self):
        resp = self.client.get("/admin/login/?next=/admin/")
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(resp["Location"].startswith(reverse("dynamic_login")))
