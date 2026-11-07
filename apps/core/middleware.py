from django.utils.cache import patch_cache_control, patch_vary_headers

CSP = (
    "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob:; connect-src 'self'; worker-src 'self' blob:; "
    "media-src 'self' blob:; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)


class HtmxSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Includes expired sessions and login forms, which can contain CSRF tokens.
        patch_cache_control(response, private=True, no_store=True)
        patch_vary_headers(response, ["HX-Request", "HX-History-Restore-Request"])
        response.setdefault("Content-Security-Policy", CSP)
        response.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=()")
        if request.htmx and response.status_code == 302 and not request.user.is_authenticated:
            # Preserve cookies and security/cache headers from the original response.
            response.status_code = 200
            response["HX-Redirect"] = response["Location"]
            del response["Location"]
        return response
