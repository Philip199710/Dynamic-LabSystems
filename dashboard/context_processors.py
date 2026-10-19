from django.conf import settings


def branding(request):
    from accounts.roles import is_dynamic_admin

    user = getattr(request, "user", None)
    return {
        "SITE_NAME": getattr(settings, "SITE_NAME", "Dynamic LabSystems"),
        "IS_DYNAMIC_ADMIN": bool(user and is_dynamic_admin(user)),
    }
