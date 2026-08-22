from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home, name="home"),
    path("analytics/", views.analytics_index, name="analytics_index"),
    path("analytics/<int:method_id>/", views.analytics_trend, name="analytics_trend"),
]
