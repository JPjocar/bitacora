# Avance al 6 de noviembre de 2026 (Lima)

| Área | Estado |
| --- | --- |
| Base de proyecto | Django, PostgreSQL, entorno, Git local, dependencias fijas, templates y estáticos |
| Usuarios | Login/logout, perfil, alta/edición/desactivación/reactivación, contraseña y auditoría |
| Roles | Tres grupos fijos, permisos, asignación por cuenta y consulta de matriz |
| Ubicaciones | Tipos, listado/detalle, filtros/paginación, alta/edición/desactivación/reactivación |
| Categorías | Catálogo inicial de seis tipos, alta/edición/desactivación e historial |
| Dispositivos | Ficha, serie opcional, código inmutable, búsqueda/filtros, fechas, archivo y consulta limitada docente |
| Movimientos | Traslados físicos con origen real, motivo, fechas, advertencia y actualización atómica de ubicación |
| QR | PNG por UUID, origen explícito, sesión y permisos por equipo |
| Etiquetas | Individuales/selección, deduplicación, A4; prueba física pendiente |
| Escáner | Cámara en modal, imagen local y código manual; pruebas JS simuladas, cámara real pendiente |
| Configuración preventiva | Único/periódico, equipos, tareas, fechas, edición/desactivación y auditoría |
| Ejecución preventiva | Seis estados, toma, inicio/reanudación, avances/notas, liberación, omisión, completado y cierre/cancelación |
| Fechas reales | Por equipo, registro anterior administrativo con motivo, cierre general independiente |
| Recurrencia | Calendario vigente por equipo, propuestas a 7 días, apertura manual de ciclos y tareas limpias |
| Historial de ejecuciones | Lista paginada, detalle por ciclo con copias originales y eventos filtrados |
| Notificaciones | Disponibilidad/liberación inmediata, fechas por comando, idempotencia, bandeja propia y contador HTMX 30 s |
| Dashboard/reportes | Inventario, vencimientos, ejecuciones, sin periódico y omisiones; filtros, CSV y HTML imprimible |
| Concurrencia | Veintisiete casos PostgreSQL; incluye comando/operación/lectura de avisos simultáneos |
| Visual | Templates responsive implementados; revisión en navegador pendiente por falta de navegador conectado |
| Despliegue | Configuración y check de seguridad; no se publicó ni validó HTTPS real |
| CI | Workflow incluido; ejecución en GitHub pendiente |
| Otros módulos | No implementados |

Séptimo incremento (fases 9–10): `notifications/0001_initial` aplicada, una tabla nueva,
sin dependencias adicionales. Roles sincronizados: admin y técnico reciben avisos y
consultan panel/reportes; docente sin acceso. Se conservaron exactamente los datos
preventivos anteriores (comparación de hashes del volcado antes/después de migrar).
Comando ejecutado dos veces: 10 nuevos, luego 0. HTTP en 8006 correcto con los tres roles.

Archivos de este incremento: `apps/notifications/` (modelo, servicios, vistas, rutas,
Admin, comando y migración); `apps/dashboard/` (filtros, consultas, vistas y reportes);
integración en `maintenance/services.py`, `execution.py`, `recurrence.py` y `selectors.py`;
permisos en `accounts/roles.py` y etiquetas en `core/templatetags/labels.py`; registro en
`config/settings.py` y `urls.py`; navegación en `templates/base.html`, plantillas en
`templates/notifications/` y `templates/dashboard/`, estilo `static/css/reports.css`;
cuatro archivos nuevos `tests/test_notification*.py`/`test_dashboard.py` y
`scripts/smoke_dashboard_http.py`. README y los nueve documentos de docs actualizados.

**353 pruebas Django aprobadas** (305 previas + 48 nuevas) y **21 pruebas JavaScript**.
Incluye 27 casos concurrentes PostgreSQL y conservación de historial al aplicar migraciones.
Última corrección de formato de fechas de reportes validada con las 22 pruebas del dashboard.

Las pruebas y resultados efectivos se registran en PRUEBAS.md. No se presenta revisión
visual simulada ni se afirma validación en el instituto.

Para continuar: leer prompt, README, este archivo y reglas; ejecutar las pruebas
existentes en PostgreSQL antes de modificar. No reemplazar el usuario personalizado,
eliminar migraciones aplicadas ni escribir directamente en datos de otro módulo.
Siguiente fase: incidencias, solo bajo encargo; todavía no se implementó. Mantener la
integración explícita de avisos y sus claves idempotentes. La fecha vigente se deriva de la
fecha real más reciente por equipo más el intervalo actual; next_due_date y due_date
de ciclos previos son copias históricas que no se reescriben. Mantener el índice de una
ejecución abierta y las guardias de versión/predecesor al integrar otros módulos.
La reversión de completados y cierres sigue bloqueada. La tarea horaria de avisos debe
activarse en el equipo piloto según MANUAL.md; sin ella no se reconcilian fechas.
La revisión visual, cámara física, impresión y despliegue HTTPS siguen pendientes.
