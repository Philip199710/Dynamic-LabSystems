from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, reverse_lazy
from django.db import connection
from django.http import HttpResponse
from django.views.generic import RedirectView

from accounts.login_views import AdminLoginView, LabLoginView, admin_console
from accounts.roles import is_dynamic_admin


def _dynamic_admins_only(request):
    """Django admin (/admin/) is for Dynamic APAC admins only, not lab staff."""
    return request.user.is_active and request.user.is_staff and is_dynamic_admin(request.user)


admin.site.has_permission = _dynamic_admins_only
admin.site.site_header = "Dynamic APAC · LabSystems administration"
admin.site.site_title = "Dynamic LabSystems admin"


def healthz(request):
    """Lightweight check Render uses before switching traffic to a new deploy:
    returns 200 only if the app is up and can reach the database."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")
    return HttpResponse("ok", content_type="text/plain")


urlpatterns = [
    path("healthz", healthz, name="healthz"),
    path("admin/login/", RedirectView.as_view(url=reverse_lazy("dynamic_login"), query_string=True)),
    path("admin/", admin.site.urls),
    path("", RedirectView.as_view(pattern_name="dashboard:home", permanent=False)),
    path("login/", LabLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("dynamic/login/", AdminLoginView.as_view(), name="dynamic_login"),
    path("dynamic/", admin_console, name="dynamic_console"),
    path("dynamic/labs/", include("labs.urls")),
    path("", include("accounts.urls")),
    path("dashboard/", include("dashboard.urls")),
    path("catalog/", include("catalog.urls")),
    path("samples/", include("samples.urls")),
    path("labtests/", include("labtests.urls")),
    path("reports/", include("reports.urls")),
    path("chat/", include("chat.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
