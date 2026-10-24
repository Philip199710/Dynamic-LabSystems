from django.urls import path

from . import views

app_name = "labs"

urlpatterns = [
    path("", views.lab_list, name="list"),
    path("<int:pk>/", views.lab_detail, name="detail"),
    path("device/<int:pk>/<str:action>/", views.device_decide, name="device_decide"),
    path("user/<int:pk>/toggle/", views.user_toggle, name="user_toggle"),
    path("signins/", views.signin_log, name="signins"),
    path("view-lab/", views.view_lab, name="view_lab"),
]
