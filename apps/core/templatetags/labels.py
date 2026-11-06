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
        "category_id": "Categoría (ID)",
        "location_id": "Ubicación (ID)",
        "movement_id": "Movimiento (ID)",
        "brand": "Marca",
        "model": "Modelo",
        "serial_number": "Número de serie",
        "technical_details": "Detalles técnicos",
        "acquired_on": "Adquisición",
        "commissioned_on": "Puesta en servicio",
        "status": "Estado operativo",
        "observations": "Observaciones",
        "reason": "Motivo",
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
        "assets.view_category": "Consultar categorías",
        "assets.add_category": "Crear categorías",
        "assets.change_category": "Editar y desactivar categorías",
        "assets.view_device": "Consultar la ficha técnica de dispositivos",
        "assets.view_device_limited": "Consultar la ficha limitada de equipos activos",
        "assets.add_device": "Registrar dispositivos",
        "assets.change_device": "Editar y desactivar dispositivos",
        "assets.update_device_operation": "Actualizar estado y observaciones de dispositivos",
        "assets.view_movement": "Consultar movimientos",
        "assets.add_movement": "Registrar traslados físicos",
    }.get(f"{permission.content_type.app_label}.{permission.codename}", permission.name)
