from django.conf import settings


def branding(request):
    return {"SITE_NAME": getattr(settings, "SITE_NAME", "Dynamic LabSystems")}
