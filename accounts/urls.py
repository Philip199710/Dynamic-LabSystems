from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.client_register, name="register"),
    path(
        "portal/login/",
        auth_views.LoginView.as_view(template_name="accounts/client_login.html"),
        name="client_login",
    ),
    path(
        "portal/logout/",
        auth_views.LogoutView.as_view(next_page="accounts:client_login"),
        name="portal_logout",
    ),
    path("portal/", views.client_portal_home, name="portal_home"),
    path("portal/samples/new/", views.client_portal_request_sample, name="portal_request_sample"),
    path("portal/sample/<int:pk>/", views.client_portal_sample_detail, name="portal_sample_detail"),
    path("portal/sample/<int:pk>/coa.pdf", views.client_portal_coa_pdf, name="portal_coa_pdf"),
    path("portal/sample-test/<int:pk>/result/", views.client_portal_enter_result, name="portal_enter_result"),
    path("clients/pending/", views.pending_clients, name="pending_clients"),
    path("clients/<int:pk>/approve/", views.approve_client, name="approve_client"),
]
