from functools import wraps

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied


def is_chat_user(user):
    """Lab staff and Dynamic admins — never client-portal accounts."""
    return user.is_authenticated and user.is_active and not hasattr(user, "client_profile")


def chat_user_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not is_chat_user(request.user):
            raise PermissionDenied
        return view(request, *args, **kwargs)

    return wrapper
