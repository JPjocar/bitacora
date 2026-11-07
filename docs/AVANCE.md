# Avance al 7 de noviembre de 2026 (Lima)

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
| Dashboard/reportes | Inventario, prevención e incidencias; filtros, CSV y HTML imprimible; recurrencia de reportes sin inválidos |
| Incidencias | Reporte por equipo, toma exclusiva, notas, liberación y cierre solucionada/no reparable/inválida-duplicada |
| Ficha integrada | Auditoría física, incidencias y preventivos paginados; docente solo ve sus reportes |
| Concurrencia | Treinta y tres casos PostgreSQL; seis nuevos de reporte, toma, notas, liberación y cierre |
| Visual | Templates responsive implementados; revisión en navegador pendiente por falta de navegador conectado |
| Piloto local | Waitress/DEBUG=False con cuenta PG restringida y Nginx HTTPS en loopback; tres roles y bloqueo 429 verificados |
| Backup/restauración | 28 tablas y un archivo media restaurados/verificados en BD temporal; fuente conservada |
| Despliegue institucional | No publicado; dominio, certificado, ACL, servicios/tareas y aceptación pendientes |
| CI | Ampliado con cliente PostgreSQL 18 y recuperación; ejecución en GitHub pendiente |
| Otros módulos | No implementados |

Noveno incremento (fase 11): 415 pruebas de base OK y **428 Django + 21 JavaScript OK**
al terminar; 33 carreras PostgreSQL conservadas. Dos fallos reproducidos/corregidos:
restauración HTMX del dashboard y caché de sesión vencida. CSP/Permissions-Policy añadidas,
sin bloquear la cámara del origen. Comprobación estructural HTML en diez rutas.

Nuevos comandos `check_pilot`, `backup_pilot`, `verify_pilot_backup`; módulo de backup
en core, servidores/configuración en scripts/deploy y dependencia separada requirements-pilot.
Sin modelos ni migraciones nuevos. MEDIA_ROOT explícito para no copiar el proyecto como media.
Pillow actualizado de 12.3.0 a 13.0.0 tras detectar avisos: auditoría final de 12 paquetes
del piloto/13 de desarrollo sin omitidos ni avisos conocidos; frontend sin avisos en OSV.
Backup/restore real: 28 tablas iguales, secuencias/restricciones y un archivo sintético,
BD temporal eliminada. Preflight runtime sin privilegios administrativos correcto;
avisos con cuenta runtime 4 nuevos y luego 0. HTTPS y tres roles verificados, 429 resiste
cabeceras de IP falsificadas. Procedimiento y límites en PILOTO.md.

Archivos: middleware core, vista dashboard, settings, tres comandos de gestión y
pilot_backup.py; manage_local.py con --env-file; scripts configure_proxy/serve_pilot/
smoke_pilot_http; soporte HTTPS en smoke_execution_http; templates/env/SQL de deploy;
tres archivos test_pilot_*.py; workflow CI, requirements-pilot y documentación.

Preparación local verificable entregada. Pendientes que requieren entorno/personas:
navegador responsive/teclado/CSP/cámara, etiquetas físicas, dominio/certificado autorizado,
ACL, recuperación cronometrada, servicio y tareas del equipo final y CI remoto. No se
afirma aceptación institucional. No se instaló servicio ni se publicó fuera de loopback.

## Registro del octavo incremento

Octavo incremento (fase 12, solicitada por el usuario): `incidents/0001_initial` y
`notifications/0002_incident_notifications` aplicadas, dos tablas nuevas y una FK nullable
de fuente en Notification. Sin dependencias adicionales. Hashes antes/después idénticos
para las nueve tablas previas verificadas (dispositivos, preventivos y avisos).
Roles sincronizados: docente reporta/sigue sus casos y recibe cierres en su bandeja;
técnico toma/atiende; administrador supervisa e interviene con motivo. Panel y reportes
completos continúan restringidos. HTTP en 8007 conserva tres incidencias sintéticas:
`/incidencias/1/` solucionada, `/incidencias/2/` no reparable y `/incidencias/3/` inválida.

Archivos: `apps/incidents/` (modelo, servicios, selectores, formularios, vistas, rutas,
Admin y migración); `notifications/models.py`, `services.py`, `views.py` y migración 0002;
`accounts/roles.py`, `core/templatetags/labels.py`; `assets/views.py` y plantilla de ficha;
`maintenance/selectors.py` para historial; filtros/consultas/vistas/reportes de dashboard;
`config/settings.py`, `urls.py`, `templates/base.html`, `templates/dashboard/results.html`
y seis plantillas nuevas en `templates/incidents/`. Cinco archivos nuevos de pruebas,
`tests/incident_helpers.py`, actualización de `test_notifications.py`, smoke HTTP nuevo
y ajuste del smoke de dashboard. README y nueve documentos de docs actualizados.

En ese incremento: **415 pruebas Django aprobadas** (353 previas + 62 nuevas) y **21 JavaScript**.
Incluye 33 casos concurrentes PostgreSQL y conservación de historial al migrar.

Las pruebas y resultados efectivos se registran en PRUEBAS.md. No se presenta revisión
visual simulada ni se afirma validación en el instituto.

Para continuar: leer prompt, README, este archivo y reglas; ejecutar las pruebas
existentes en PostgreSQL antes de modificar. No reemplazar el usuario personalizado,
eliminar migraciones aplicadas ni escribir directamente en datos de otro módulo.
Continuidad: completar la aceptación visual/física en el entorno autorizado; no se
ejecutó un despliegue institucional. Mantener integración explícita
de avisos y claves idempotentes. La fecha vigente preventiva se deriva de la
fecha real más reciente por equipo más el intervalo actual; next_due_date y due_date
de ciclos previos son copias históricas que no se reescriben. Mantener el índice de una
ejecución abierta y las guardias de versión/predecesor al integrar otros módulos.
La reversión de completados/cierres e incidencias cerradas sigue bloqueada. La tarea horaria de avisos debe
activarse en el equipo piloto según MANUAL.md; sin ella no se reconcilian fechas.
La revisión visual, cámara física, impresión y despliegue HTTPS siguen pendientes.
