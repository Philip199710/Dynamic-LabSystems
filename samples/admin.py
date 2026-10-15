from django.contrib import admin

from .models import ChainOfCustodyEntry, Sample


class CustodyInline(admin.TabularInline):
    model = ChainOfCustodyEntry
    extra = 0
    readonly_fields = ("actor", "action", "notes", "timestamp")
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Sample)
class SampleAdmin(admin.ModelAdmin):
    list_display = ("sample_id", "fuel_type", "source", "status", "date_received", "received_by")
    list_filter = ("status", "fuel_type")
    search_fields = ("sample_id", "source")
    readonly_fields = ("sample_id",)
    inlines = [CustodyInline]

    # Lab records are kept permanently: samples can be marked Disposed,
    # but never deleted.
    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ChainOfCustodyEntry)
class ChainOfCustodyEntryAdmin(admin.ModelAdmin):
    list_display = ("sample", "action", "actor", "timestamp")
    list_filter = ("action",)

    # The chain of custody is an append-only audit trail.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
