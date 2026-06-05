class LoginRequiredMiddleware:
    """Redirect unauthenticated users to the admin login page for all app views.

    Django's /admin/ handles its own authentication, so it is explicitly exempt.
    The /health/ endpoint must stay public for Render's health checks.
    """

    EXEMPT_PREFIXES = ('/admin/', '/health/')

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not request.user.is_authenticated:
            if not any(request.path.startswith(p) for p in self.EXEMPT_PREFIXES):
                from django.shortcuts import redirect
                return redirect(f'/admin/login/?next={request.path}')
        return self.get_response(request)
