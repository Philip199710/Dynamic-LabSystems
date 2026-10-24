from django.conf import settings


def branding(request):
    from accounts.roles import is_dynamic_admin

    user = getattr(request, "user", None)
    admin = bool(user and is_dynamic_admin(user))
    ctx = {
        "SITE_NAME": getattr(settings, "SITE_NAME", "Dynamic LabSystems"),
        "IS_DYNAMIC_ADMIN": admin,
        "CURRENT_LAB": getattr(request, "lab", None) if user and user.is_authenticated else None,
    }
    if admin:
        from labs.models import Lab

        ctx["ALL_LABS"] = list(Lab.objects.only("id", "name", "code"))
    return ctx
