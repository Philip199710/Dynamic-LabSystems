import time
from importlib import import_module

from django.conf import settings
from django.contrib.sessions.backends.base import UpdateError
from django.contrib.sessions.exceptions import SessionInterrupted
from django.shortcuts import redirect
from django.utils.cache import patch_vary_headers
from django.utils.deprecation import MiddlewareMixin
from django.utils.http import http_date

# URL prefixes a client-portal account may reach. Anything else (the
# internal dashboard, sample list, admin, etc.) redirects to their portal —
# this is the actual access boundary; the client-only views additionally
# scope every query to request.user.client_profile.client so even within
# /portal/ one client can never see another's samples.
CLIENT_ALLOWED_PREFIXES = ("/portal/", "/static/", "/media/")

PORTAL_SESSION_COOKIE_NAME = "portal_sessionid"
PORTAL_PATH_PREFIX = "/portal/"


class PortalSessionMiddleware(MiddlewareMixin):
    """Gives the client portal its own session cookie, so staff and client
    logins can coexist in the same browser.

    Django's session framework has exactly one SESSION_COOKIE_NAME, shared
    by every login on the site. That's fine when there's one kind of user,
    but here a Lab Manager and a client are different accounts that both
    need to be signed in at once — e.g. a staff member checking the portal
    in another tab shouldn't be silently logged out of /samples/. Under
    Django's default cookie, whichever login happens *last* wins, because
    both write the same "sessionid" cookie.

    The fix: requests under /portal/ get a second, independent cookie
    ("portal_sessionid") instead of the default one; everything else keeps
    using the normal "sessionid" cookie. Nothing downstream has to know —
    AuthenticationMiddleware, @login_required, django.contrib.auth.login()/
    logout(), and every view all just read/write request.session as usual.
    This is a drop-in replacement for
    django.contrib.sessions.middleware.SessionMiddleware (same logic, just
    with a cookie name chosen per-request); it must sit in that exact spot
    in MIDDLEWARE, before AuthenticationMiddleware.
    """

    def __init__(self, get_response):
        super().__init__(get_response)
        engine = import_module(settings.SESSION_ENGINE)
        self.SessionStore = engine.SessionStore

    @staticmethod
    def cookie_name_for(request):
        if request.path.startswith(PORTAL_PATH_PREFIX):
            return PORTAL_SESSION_COOKIE_NAME
        return settings.SESSION_COOKIE_NAME

    def process_request(self, request):
        cookie_name = self.cookie_name_for(request)
        request.session = self.SessionStore(request.COOKIES.get(cookie_name))

    def process_response(self, request, response):
        try:
            accessed = request.session.accessed
            modified = request.session.modified
            empty = request.session.is_empty()
        except AttributeError:
            return response

        cookie_name = self.cookie_name_for(request)
        if cookie_name in request.COOKIES and empty:
            response.delete_cookie(
                cookie_name,
                path=settings.SESSION_COOKIE_PATH,
                domain=settings.SESSION_COOKIE_DOMAIN,
                samesite=settings.SESSION_COOKIE_SAMESITE,
            )
            patch_vary_headers(response, ("Cookie",))
        else:
            if accessed:
                patch_vary_headers(response, ("Cookie",))
            if (modified or settings.SESSION_SAVE_EVERY_REQUEST) and not empty:
                if request.session.get_expire_at_browser_close():
                    max_age = None
                    expires = None
                else:
                    max_age = request.session.get_expiry_age()
                    expires = http_date(time.time() + max_age)
                if response.status_code < 500:
                    try:
                        request.session.save()
                    except UpdateError:
                        raise SessionInterrupted(
                            "The request's session was deleted before the "
                            "request completed. The user may have logged "
                            "out in a concurrent request, for example."
                        )
                    response.set_cookie(
                        cookie_name,
                        request.session.session_key,
                        max_age=max_age,
                        expires=expires,
                        domain=settings.SESSION_COOKIE_DOMAIN,
                        path=settings.SESSION_COOKIE_PATH,
                        secure=settings.SESSION_COOKIE_SECURE or None,
                        httponly=settings.SESSION_COOKIE_HTTPONLY or None,
                        samesite=settings.SESSION_COOKIE_SAMESITE,
                    )
        return response


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
