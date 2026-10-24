from .access import is_chat_user
from .services import unread_by_channel


def chat_unread(request):
    user = getattr(request, "user", None)
    if user is None or not is_chat_user(user) or request.path.startswith(("/admin/", "/portal/")):
        return {}
    try:
        return {"CHAT_UNREAD": sum(unread_by_channel(user, getattr(request, "lab", None)).values())}
    except Exception:  # never let the badge break a page
        return {}
