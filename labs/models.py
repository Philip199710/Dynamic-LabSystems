"""Labs (customers), their licences, approved devices and the sign-in log.

Each customer lab sees only its own samples, instruments, chat and clients.
Licences are sold per lab, per location, per login: a Lab has a limit on
active staff logins, and each login works only on the PC(s) approved for it.
"""

import hashlib
import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone


class Lab(models.Model):
    name = models.CharField(max_length=150, unique=True)
    code = models.CharField(max_length=20, unique=True, help_text="Short code, e.g. SSD-JUBA")
    location = models.CharField(max_length=150, blank=True, help_text="City / site")
    country = models.CharField(max_length=80, blank=True)
    contact_email = models.EmailField(blank=True)
    max_logins = models.PositiveIntegerField(default=5, help_text="Licensed staff logins (active accounts)")
    devices_per_login = models.PositiveIntegerField(default=1, help_text="PCs each login may be approved on")
    auto_approve_first_device = models.BooleanField(
        default=True, help_text="Approve a login's first PC automatically; later PCs need Dynamic approval"
    )
    is_active = models.BooleanField(default=True, help_text="Untick to suspend the lab (staff can't sign in)")
    licence_expires = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def licence_valid(self):
        if not self.is_active:
            return False
        return not (self.licence_expires and self.licence_expires < timezone.localdate())

    def active_logins(self):
        return self.members.filter(user__is_active=True).count()

    def seats_left(self):
        return max(0, self.max_logins - self.active_logins())


class LabMember(models.Model):
    """Which lab a staff login belongs to (one lab per login)."""

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lab_membership")
    lab = models.ForeignKey(Lab, on_delete=models.PROTECT, related_name="members")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.get_username()} @ {self.lab.code}"


def hash_key(raw):
    return hashlib.sha256(raw.encode()).hexdigest()


def new_device_key():
    return secrets.token_urlsafe(32)


class Device(models.Model):
    STATUS_PENDING = "PENDING"
    STATUS_APPROVED = "APPROVED"
    STATUS_REVOKED = "REVOKED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Waiting for approval"),
        (STATUS_APPROVED, "Approved"),
        (STATUS_REVOKED, "Revoked"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="devices")
    key_hash = models.CharField(max_length=64, db_index=True)
    label = models.CharField(max_length=150, blank=True, help_text="Browser / operating system")
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default=STATUS_PENDING)
    first_ip = models.GenericIPAddressField(null=True, blank=True)
    last_ip = models.GenericIPAddressField(null=True, blank=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    decided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    decided_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-first_seen"]
        unique_together = [("user", "key_hash")]

    def __str__(self):
        return f"{self.user.get_username()} · {self.label or 'device'} ({self.get_status_display()})"


class LoginEvent(models.Model):
    OUTCOME_OK = "OK"
    OUTCOME_PENDING = "PENDING_DEVICE"
    OUTCOME_BLOCKED = "BLOCKED"
    OUTCOME_FAILED = "FAILED"
    OUTCOME_CHOICES = [
        (OUTCOME_OK, "Signed in"),
        (OUTCOME_PENDING, "New PC — waiting for approval"),
        (OUTCOME_BLOCKED, "Blocked"),
        (OUTCOME_FAILED, "Wrong password"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="login_events")
    username = models.CharField(max_length=150)
    lab = models.ForeignKey(Lab, on_delete=models.SET_NULL, null=True, blank=True, related_name="login_events")
    device = models.ForeignKey(Device, on_delete=models.SET_NULL, null=True, blank=True, related_name="login_events")
    outcome = models.CharField(max_length=20, choices=OUTCOME_CHOICES)
    detail = models.CharField(max_length=200, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    city = models.CharField(max_length=100, blank=True)
    country = models.CharField(max_length=100, blank=True)
    user_agent = models.CharField(max_length=300, blank=True)
    new_network = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.username} {self.outcome}"

    @property
    def place(self):
        return ", ".join(p for p in (self.city, self.country) if p)
