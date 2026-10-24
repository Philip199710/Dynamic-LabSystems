"""Team chat for lab staff (channels + messages), modelled on Dynamic OpsHub.

Messages are part of the lab record: they're never deleted, and the admin
is read-only for them. Delivery is by short polling, so there's nothing
extra to run on Render (no Redis, no websockets).
"""

from django.conf import settings
from django.db import models


class Channel(models.Model):
    lab = models.ForeignKey("labs.Lab", on_delete=models.PROTECT, null=True, blank=True, related_name="channels")
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    is_archived = models.BooleanField(default=False)

    class Meta:
        ordering = ["name"]
        unique_together = [("lab", "name")]

    def __str__(self):
        return f"#{self.name}"


class Message(models.Model):
    channel = models.ForeignKey(Channel, on_delete=models.PROTECT, related_name="messages")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name="chat_messages"
    )
    body = models.TextField(max_length=4000)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["id"]
        indexes = [models.Index(fields=["channel", "id"])]

    def __str__(self):
        return f"{self.channel} · {self.author} · {self.created_at:%Y-%m-%d %H:%M}"


class ReadState(models.Model):
    """The last message each person has seen in each channel (drives unread badges)."""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="chat_read_states")
    channel = models.ForeignKey(Channel, on_delete=models.CASCADE, related_name="read_states")
    last_read_id = models.BigIntegerField(default=0)

    class Meta:
        unique_together = [("user", "channel")]
