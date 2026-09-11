from django.urls import path

from . import views

app_name = "catalog"

urlpatterns = [
    path("instruments/", views.instrument_list, name="instrument_list"),
    path("instruments/<int:pk>/", views.instrument_detail, name="instrument_detail"),
]
