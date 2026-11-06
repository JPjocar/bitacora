from calendar import monthrange
from datetime import date, timedelta

from django.core.exceptions import ValidationError


def add_interval(base, value, unit):
    """Calendar months clamp the day, without approximating a month as 30 days."""
    if type(base) is not date or type(value) is not int or value <= 0:
        raise ValidationError("Indique una fecha válida y un intervalo entero positivo.")
    try:
        if unit == "DIAS":
            return base + timedelta(days=value)
        if unit == "MESES":
            year, month = divmod(base.year * 12 + base.month - 1 + value, 12)
            month += 1
            return date(year, month, min(base.day, monthrange(year, month)[1]))
    except (ValueError, OverflowError) as error:
        raise ValidationError(
            "El intervalo produce una fecha fuera del rango permitido."
        ) from error
    raise ValidationError("Seleccione días o meses como unidad del intervalo.")
