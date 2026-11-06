from django import template

register = template.Library()


@register.filter
def field_label(value):
    return {
        "username": "Usuario",
        "first_name": "Nombres",
        "last_name": "Apellidos",
        "email": "Correo",
        "is_active": "Activo",
        "role": "Rol",
        "name": "Nombre",
        "code": "Código",
        "kind": "Tipo",
        "description": "Descripción",
    }.get(value, value)


@register.filter
def event_value(value):
    if value is None or value == "":
        return "—"
    if isinstance(value, bool):
        return "Sí" if value else "No"
    return value


@register.filter
def permission_label(permission):
    return {
        "accounts.add_user": "Crear usuarios",
        "accounts.change_user": "Editar y desactivar usuarios; restablecer contraseñas",
        "accounts.view_user": "Consultar usuarios",
        "accounts.assign_role": "Asignar roles de negocio",
        "auth.view_group": "Consultar roles y permisos",
        "locations.view_location": "Consultar ubicaciones",
        "locations.add_location": "Crear ubicaciones",
        "locations.change_location": "Editar, desactivar y reactivar ubicaciones",
    }.get(f"{permission.content_type.app_label}.{permission.codename}", permission.name)
