from django.conf import settings
from django.core.checks import Error, register
from django.core.exceptions import ImproperlyConfigured

from .qr import public_origin


@register()
def check_public_url(app_configs, **kwargs):
    try:
        public_origin()
    except ImproperlyConfigured as error:
        return [Error(str(error), id="assets.E001")]
    return []


@register(deploy=True)
def check_public_https(app_configs, **kwargs):
    if not settings.BITACORA_PUBLIC_URL.startswith("https://"):
        return [Error("En producción BITACORA_PUBLIC_URL debe usar HTTPS.", id="assets.E002")]
    return []
