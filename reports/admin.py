from django.contrib import admin

from .models import Certificate


@admin.register(Certificate)
class CertificateAdmin(admin.ModelAdmin):
    list_display = ("certificate_number", "sample", "issued_at", "issued_by")
    list_select_related = ("sample", "issued_by")
    search_fields = ("certificate_number", "sample__sample_id")
    readonly_fields = ("certificate_number", "issued_at")
