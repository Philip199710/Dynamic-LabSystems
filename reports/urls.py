from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("sample/<int:pk>/coa.pdf", views.sample_coa_pdf, name="coa_pdf"),
    path("sample/<int:pk>/coa/preview/", views.sample_coa_preview, name="coa_preview"),
]
