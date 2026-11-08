"""Shared presentation only: statuses never change domain state or permissions."""

from django import template
from django.utils import timezone

register = template.Library()

STATES = {
    "OPERATIVO": ("Operativo", "success"),
    "CON_OBSERVACIONES": ("Con observaciones", "warning"),
    "FUERA_DE_SERVICIO": ("Fuera de servicio", "danger"),
    "RETIRADO_DEL_CONTROL_OPERATIVO": ("Retirado del control operativo", "secondary"),
    "PENDIENTE_ATENCION": ("Pendiente de atención", "warning"),
    "ASIGNADO": ("Asignado", "info"),
    "EN_EJECUCION": ("En ejecución", "primary"),
    "EN_ATENCION": ("En atención", "primary"),
    "COMPLETADO": ("Completado", "success"),
    "COMPLETADO_PARCIALMENTE": ("Completado parcialmente", "warning"),
    "CANCELADO": ("Cancelado", "secondary"),
    "CERRADA": ("Cerrada", "secondary"),
    "SIN_FINALIZAR": ("Sin finalizar", "warning"),
    "OMITIDO": ("Omitido", "secondary"),
    "SOLUCIONADA": ("Solucionada", "success"),
    "NO_REPARABLE": ("No reparable", "danger"),
    "INVALIDA_DUPLICADA": ("Inválida o duplicada", "secondary"),
}


@register.inclusion_tag("components/status_badge.html")
def status_badge(value, kind="state", label=None):
    if kind == "active":
        text, color = ("Activo", "success") if value else ("Inactivo", "danger")
    elif kind == "task":
        text, color = ("Realizada", "success") if value else ("Pendiente", "warning")
    else:
        text, color = STATES.get(value, (value or "Sin ejecución", "secondary"))
    return {"label": label or text, "color": color}


@register.inclusion_tag("components/deadline.html")
def deadline(value, today=None, show_date=True):
    """Relative civil dates in Lima; a deadline is never an execution status."""
    if not value:
        return {}
    days = (value - (today or timezone.localdate())).days
    if days < 0:
        count = -days
        label = f"Vencido hace {count} día{'s' if count != 1 else ''}"
        color = "danger"
    elif days == 0:
        label, color = "Hoy", "warning"
    elif days == 1:
        label, color = "Mañana", "warning"
    else:
        label, color = f"En {days} días", "warning" if days <= 7 else "info"
    return {"due_date": value, "label": label, "color": color, "show_date": show_date}


@register.filter
def person_name(user):
    return (user.get_full_name().strip() or user.username) if user else "Sin asignar"
