"""QR identity and label services. No stored image or batch business entity."""

import base64
import re
from io import BytesIO
from urllib.parse import urlsplit
from uuid import UUID

import qrcode
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import URLValidator
from django.urls import Resolver404, resolve, reverse
from qrcode.image.pil import PilImage

from apps.core.permissions import require_permission

from .selectors import visible_devices

MAX_LABELS = 100
SCAN_ERROR = "Código no reconocido o equipo no disponible para tu cuenta."


def public_origin():
    value = settings.BITACORA_PUBLIC_URL
    try:
        URLValidator(schemes=["https", "http"])(value)
        parts = urlsplit(value)
        if (
            len(value) > 200
            or any(c.isspace() or ord(c) < 32 for c in value)
            or "\\" in value
            or parts.username is not None
            or parts.password is not None
            or parts.path not in ("", "/")
            or "?" in value
            or "#" in value
        ):
            raise ValueError
        # Accessing port also validates its range.
        _ = parts.port
    except (ValidationError, ValueError, TypeError) as error:
        raise ImproperlyConfigured(
            "BITACORA_PUBLIC_URL debe ser un origen absoluto sin ruta, credenciales ni "
            "parámetros (máximo 200 caracteres)."
        ) from error
    return value.rstrip("/")


def device_url(device):
    return public_origin() + reverse("assets:detail", kwargs={"public_id": device.public_id})


def device_qr_png(device):
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(device_url(device))
    qr.make(fit=True)
    image = qr.make_image(image_factory=PilImage, fill_color="black", back_color="white")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def label_sheets(*, actor, identifiers):
    actor = require_permission(actor, "assets.print_device_label")
    if not identifiers or len(identifiers) > MAX_LABELS:
        raise ValidationError(f"Selecciona entre 1 y {MAX_LABELS} equipos para imprimir.")
    try:
        selected = {UUID(str(value)) for value in identifiers}
    except (ValueError, TypeError, AttributeError) as error:
        raise ValidationError("La selección de equipos no es válida.") from error
    devices = list(visible_devices(actor).filter(public_id__in=selected).order_by("code"))
    if len(devices) != len(selected):
        raise ValidationError("Hay equipos inexistentes o no disponibles en la selección.")
    labels = [
        {"device": device, "png": base64.b64encode(device_qr_png(device)).decode("ascii")}
        for device in devices
    ]
    return [labels[start : start + 15] for start in range(0, len(labels), 15)]


def _origin_key(parts):
    return (
        parts.scheme.lower(),
        parts.hostname,
        parts.port if parts.port is not None else (443 if parts.scheme == "https" else 80),
    )


def resolve_scan(*, actor, value):
    devices = visible_devices(actor)
    value = value.strip()
    if re.fullmatch(r"EQ-[ABCDEFGHJKMNPQRSTUVWXYZ23456789]{8}", value.upper()):
        device = devices.filter(code=value.upper()).first()
    else:
        try:
            if (
                len(value) > 2048
                or any(c.isspace() or ord(c) < 32 for c in value)
                or "\\" in value
                or "?" in value
                or "#" in value
            ):
                raise ValueError
            parts = urlsplit(value)
            if (
                parts.username is not None
                or parts.password is not None
                or _origin_key(parts) != _origin_key(urlsplit(public_origin()))
            ):
                raise ValueError
            match = resolve(parts.path)
            if match.view_name != "assets:detail" or parts.path != reverse(
                "assets:detail", kwargs=match.kwargs
            ):
                raise ValueError
        except (ValueError, Resolver404) as error:
            raise ValidationError(SCAN_ERROR) from error
        device = devices.filter(public_id=match.kwargs["public_id"]).first()
    if device is None:
        raise ValidationError(SCAN_ERROR)
    # Never redirect to untrusted text: return the existing device identity instead.
    return device
