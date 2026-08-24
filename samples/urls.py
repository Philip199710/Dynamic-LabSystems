from django.urls import path

from . import views

app_name = "samples"

urlpatterns = [
    path("", views.sample_list, name="list"),
    path("new/", views.sample_create, name="create"),
    path("<int:pk>/", views.sample_detail, name="detail"),
    path("<int:pk>/dispose/", views.sample_dispose, name="dispose"),
    path("<int:pk>/delete/", views.sample_delete, name="delete"),
]
