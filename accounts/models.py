from django.conf import settings
from django.db import models


class Client(models.Model):
    """An external client organization that submits samples for testing.

    Distinct from samples.Sample.source (a free-text description staff type
    when registering a sample, e.g. "Retail station #14") — a Client is a
    real account-holding organization with its own portal logins. Linking a
    Sample to a Client (samples.Sample.client) is what makes that sample
    visible in that client's portal.
    """

    name = models.CharField(max_length=150, unique=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=40, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class ClientProfile(models.Model):
    """Links a portal-registered User to their Client organization, and
    gates portal access behind staff approval.

    Self-registration (accounts:register) creates the User and this profile
    together with is_approved=False — the account exists but can't see any
    data until a Lab Manager/QA approves it (accounts:approve_client).
    """

    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="client_profile")
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="portal_users")
    is_approved = models.BooleanField(default=False)
    requested_at = models.DateTimeField(auto_now_add=True)
    approved_at = models.DateTimeField(null=True, blank=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="client_approvals_made",
    )

    class Meta:
        ordering = ["-requested_at"]

    def __str__(self):
        status = "approved" if self.is_approved else "pending"
        return f"{self.user.get_username()} · {self.client.name} ({status})"

    def approve(self, actor):
        from django.utils import timezone

        self.is_approved = True
        self.approved_at = timezone.now()
        self.approved_by = actor
        self.save(update_fields=["is_approved", "approved_at", "approved_by"])
