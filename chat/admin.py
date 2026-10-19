from django.contrib import admin

from .models import Channel, Message


@admin.register(Channel)
class ChannelAdmin(admin.ModelAdmin):
    list_display = ("name", "description", "is_archived", "created_by", "created_at")
    list_filter = ("is_archived",)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    """Read-only: chat is part of the permanent lab record."""

    list_display = ("created_at", "channel", "author", "body")
    list_filter = ("channel",)
    search_fields = ("body",)
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
