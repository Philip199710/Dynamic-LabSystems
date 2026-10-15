from django.contrib import admin

from .models import SampleTest, TestResult


class TestResultInline(admin.StackedInline):
    """Results are view-only in the admin: they are entered and amended
    through the lab screens, which log every change to the sample's chain
    of custody. Deleting a result is never allowed."""

    model = TestResult
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(SampleTest)
class SampleTestAdmin(admin.ModelAdmin):
    list_display = ("sample", "test_method", "assigned_to", "status", "due_date")
    list_filter = ("status", "test_method")
    search_fields = ("sample__sample_id",)
    inlines = [TestResultInline]

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(TestResult)
class TestResultAdmin(admin.ModelAdmin):
    list_display = ("sample_test", "value", "entered_by", "entered_at")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
