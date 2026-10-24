"""Which lab's data the current request sees."""

from accounts.roles import is_dynamic_admin

from .models import Lab

ADMIN_VIEW_LAB_KEY = "dynamic_view_lab_id"


def lab_for_user(user, session=None):
    if not getattr(user, "is_authenticated", False):
        return None
    profile = getattr(user, "client_profile", None)
    if profile is not None:
        return profile.client.lab
    membership = getattr(user, "lab_membership", None)
    if membership is not None:
        return membership.lab
    if is_dynamic_admin(user):
        lab_id = session.get(ADMIN_VIEW_LAB_KEY) if session is not None else None
        lab = Lab.objects.filter(pk=lab_id).first() if lab_id else None
        return lab or Lab.objects.order_by("id").first()
    return None


def scoped(qs, request, path="lab"):
    """Filter a queryset to the request's lab (nothing if it has no lab)."""
    lab = getattr(request, "lab", None)
    if lab is None:
        return qs.none()
    return qs.filter(**{path: lab})
