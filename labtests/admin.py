from django.contrib import admin

from .models import SampleTest, TestResult


class TestResultInline(admin.StackedInline):
    model = TestResult
    extra = 0


@admin.register(SampleTest)
class SampleTestAdmin(admin.ModelAdmin):
    list_display = ("sample", "test_method", "assigned_to", "status", "due_date")
    list_filter = ("status", "test_method")
    search_fields = ("sample__sample_id",)
    inlines = [TestResultInline]


@admin.register(TestResult)
class TestResultAdmin(admin.ModelAdmin):
    list_display = ("sample_test", "value", "entered_by", "entered_at")
