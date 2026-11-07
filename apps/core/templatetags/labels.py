from django import template

register = template.Library()


@register.filter
def event_action(value):
    return {
        "TAKEN": "Mantenimiento tomado",
        "INC_CREATED": "Incidencia reportada",
        "INC_TAKEN": "Incidencia tomada",
        "INC_RELEASED": "Incidencia liberada",
        "INC_NOTE": "Nota técnica registrada",
        "INC_CLOSED": "Incidencia cerrada",
        "STARTED": "Trabajo iniciado",
        "RESUMED": "Trabajo reanudado",
        "RELEASED": "Responsable liberado",
        "PROGRESS": "Avance registrado",
        "DEVICE_COMPLETED": "Equipo completado",
        "DEVICE_OMITTED": "Equipo omitido",
        "COMPLETED": "Mantenimiento completado",
        "PARTIALLY_COMPLETED": "Mantenimiento completado parcialmente",
        "CANCELLED": "Mantenimiento cancelado",
        "RUN_CREATED": "Siguiente ejecución creada",
    }.get(value, value)


@register.filter
def field_label(value):
    return {
        "username": "Usuario",
        "symptoms": "Síntomas",
        "note": "Nota técnica interna",
        "summary": "Resumen",
        "outcome": "Resultado de cierre",
        "incident_version": "Versión de la incidencia",
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
        "is_recurring": "Periódico",
        "base_date": "Fecha base",
        "planned_date": "Fecha prevista",
        "run_number": "Número de ejecución",
        "due_dates": "Vencimientos por equipo",
        "interval_value": "Intervalo",
        "interval_unit": "Unidad",
        "devices": "Equipos inscritos (ID)",
        "tasks": "Tareas",
        "state": "Estado de ejecución",
        "responsible_id": "Responsable (ID)",
        "started_at": "Primer inicio real",
        "completed_at": "Cierre general",
        "cancelled_at": "Cancelación",
        "execution_version": "Versión de ejecución",
        "notes": "Notas técnicas",
        "participant_id": "Equipo de la ejecución (ID)",
        "device_executed_on": "Fecha real de finalización del equipo",
        "completion_summary": "Resumen y verificación",
        "next_due_date": "Próximo vencimiento calculado",
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
        "notifications.view_notification": "Consultar y marcar sus notificaciones internas",
        "incidents.add_incident": "Reportar incidencias desde un equipo",
        "incidents.view_incident": "Consultar todas las incidencias e historial técnico",
        "incidents.view_own_incident": "Consultar y seguir sus propias incidencias",
        "incidents.take_incident": "Tomar incidencias como técnico",
        "incidents.attend_incident": "Atender las incidencias de las que es responsable",
        "incidents.override_incident": "Intervenir en incidencias con motivo administrativo",
        "incidents.close_unrepairable_incident": "Cerrar como no reparable con justificación",
        "maintenance.add_maintenance": "Configurar mantenimientos preventivos",
        "maintenance.create_next_run": "Crear manualmente la siguiente ejecución preventiva",
        "maintenance.take_maintenance": "Tomar mantenimiento como técnico",
        "maintenance.execute_maintenance": "Ejecutar el mantenimiento del que es responsable",
        "maintenance.override_maintenance": "Intervenir sobre otro responsable con motivo",
        "maintenance.backdate_maintenance": "Registrar fecha anterior con justificación",
        "maintenance.change_maintenance": "Editar y desactivar configuraciones preventivas",
        "maintenance.view_maintenance": "Consultar mantenimientos preventivos e historial",
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
