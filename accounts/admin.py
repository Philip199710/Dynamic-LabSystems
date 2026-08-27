from django.contrib import admin

from .models import Client, ClientProfile


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "contact_email", "contact_phone", "created_at")
    search_fields = ("name", "contact_email")


@admin.register(ClientProfile)
class ClientProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "client", "is_approved", "requested_at", "approved_at", "approved_by")
    list_filter = ("is_approved", "client")
    search_fields = ("user__username", "user__email", "client__name")
