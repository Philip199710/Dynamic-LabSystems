from django.shortcuts import redirect

# URL prefixes a client-portal account may reach. Anything else (the
# internal dashboard, sample list, admin, etc.) redirects to their portal —
# this is the actual access boundary; the client-only views additionally
# scope every query to request.user.client_profile.client so even within
# /portal/ one client can never see another's samples.
CLIENT_ALLOWED_PREFIXES = ("/portal/", "/logout/", "/static/", "/media/")


class ClientPortalAccessMiddleware:
    """Confines client-portal accounts to /portal/ (and logout/static/media).

    Client accounts share the same Django User table and login as everyone
    else, so without this a client could browse straight to /samples/ or
    /admin/ and see every client's data. Must sit after
    AuthenticationMiddleware (needs request.user).
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user is not None and getattr(user, "is_authenticated", False):
            profile = getattr(user, "client_profile", None)
            if profile is not None and not request.path.startswith(CLIENT_ALLOWED_PREFIXES):
                return redirect("accounts:portal_home")
        return self.get_response(request)
