from django.http import HttpResponse
from django.utils.cache import patch_cache_control


class HtmxSessionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if request.user.is_authenticated:
            patch_cache_control(response, private=True, no_store=True)
        if request.htmx and response.status_code == 302 and not request.user.is_authenticated:
            return HttpResponse(status=200, headers={"HX-Redirect": response["Location"]})
        return response
