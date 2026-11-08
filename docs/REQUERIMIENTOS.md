# Requisitos y trazabilidad

**Ajuste de interfaz solicitado el 08/11/2026:** `tests/test_ui.py` verifica estados con
etiquetas consistentes (RF-002/003/011/024), navegación según permisos (RF-001), campo
de puesta en servicio retirado sin pérdida histórica (RF-003), contexto y extractos
seguros en avisos (RF-020/021/024), responsables y fechas por equipo visibles en la lista
(RF-010/012/022) y reportes HTML con etiquetas conservando CSV simple (RF-022).
No modifica reglas de archivado. Resultados en [PRUEBAS.md](PRUEBAS.md).

| RF | Alcance entregado | Criterio de aceptación | Evidencia |
| --- | --- | --- | --- |
| RF-001 | Login/logout, perfil, cuentas y roles | Sin permisos no se ejecuta operación; roles reales, sesión y contraseñas protegidas | `tests/test_accounts.py`, `tests/test_security.py` |
| RF-002 | Ubicaciones y desactivación | Nombre/tipo válidos, unicidad, consulta y actualización autorizadas; historial conservado | `tests/test_locations.py` |
| RF-003 | Categorías y dispositivos | Ficha con serie/detalles opcionales y roles; archivo sin borrado | `tests/test_assets.py`, `tests/test_asset_views.py` |
| RF-004 | Código único y búsqueda manual | Generación criptográfica, colisión reintentada, identidad inmutable, búsqueda sin distinguir caja/espacios | Pruebas de colisión, inmutabilidad y filtros |
| RF-005 | Traslado transaccional | Origen vigente, destino válido, historial y ubicación atómicos; sin sobrescritura concurrente | `tests/test_movements.py`, `tests/test_asset_concurrency.py` |
| RF-006 | QR y etiquetas por selección | PNG decodificable, identidad estable, sesión, permisos, deduplicación y paginación de etiquetas | `tests/test_qr.py`; impresión física pendiente |
| RF-007 | Escáner cámara/imagen/manual | Validación de origen/objeto, cierre y fallbacks; sin navegación externa | `tests/test_qr.py`, `tests/js/`; cámara y móvil físicos pendientes |
| RF-008 | Único/periódico con 1 o N equipos | Permisos, fechas consistentes, atomicidad, reintentos seguros | Tests de maintenance, vistas y concurrencia |
| RF-009 | Tareas individuales/generales/por categoría | Cobertura por equipo, orden, opcionalidad y copias independientes | Grupo heterogéneo, formset, edición futura y conservación |
| RF-010 | Vencimiento vigente por equipo | Fecha real más reciente + intervalo actual o base + intervalo; omitidos/cancelados no anclan fechas | CalendarTests, test_recurrence.py |
| RF-011 | Primera y siguientes ejecuciones manuales | Copias independientes, tareas limpias, sin duplicación ni ciclos futuros del único; historial por ejecución | Tests de recurrencia, vistas, concurrencia y migración |
| RF-020 | Situación temporal y avisos por equipo | Fechas vigentes, ventana de 7 días, hoy/vencido; comando idempotente sin crear ciclos | test_recurrence_views.py, test_notifications.py |
| RF-021 | Avisos internos y lectura | Disponibilidad/liberación preventiva y correctiva, cierre al reportante; bandeja propia por permisos de fuente | test_notifications.py, test_incidents.py, test_incident_views.py |
| RF-022 | Dashboard y reportes básicos | Conteos operativos, filtros, tablas paginadas, CSV seguro y HTML imprimible | test_dashboard.py, smoke_dashboard_http.py |
| RF-012 | Toma por técnico | Exclusiva, sin inicio implícito, permisos y versión | test_execution.py, test_execution_concurrency.py |
| RF-013 | Inicio/reanudación | Primer inicio inmutable, eventos RESUMED después de liberar | Dominio y flujo HTTP |
| RF-014 | Tareas/notas | Solo responsable o admin justificado, ejecución iniciada, auditoría y rectificación con motivo | test_execution.py, test_execution_views.py |
| RF-015 | Liberación | Quita asignación, conserva primer inicio/checks/notas y registra cada liberación | Tests de dominio/concurrencia y HTTP |
| RF-016 | Omisión | Motivo y conservación de fila/vencimiento sin ejecución real | Dominio, vistas, carrera contra completado |
| RF-017 | Completar equipo | Tareas obligatorias, verificación, evidencia y fecha real autorizada | Dominio y vistas |
| RF-018 | Cierre total/parcial | Sin pendientes, tareas generales cumplidas, cancelación sin invalidar trabajo válido | Dominio, vistas y carrera contra rectificación |
| RF-019 (ejecución) | Eventos operativos | Actor/fecha, cambios previos, atomicidad e inmutabilidad | Tests de ejecución/rollback |
| RF-019 (preventivos parcial) | Auditoría de configuración | Actor/fecha/cambios, inmutabilidad y rollback | test_maintenance.py |
| RF-019 (parcial) | Auditoría de usuarios, ubicaciones, categorías y equipos | Actor/fecha y cambios atómicos, eventos no editables y relaciones PROTECT | Pruebas de rollback, retención y eventos |
| RF-019 (incidencias) | Eventos correctivos | Reporte, toma, nota, liberación y cierre con actor/fecha/versión, retención y atomicidad | test_incidents.py |
| RF-023 | Reportar desde QR/código | Reutiliza escáner y ficha; síntomas válidos, equipo autorizado activo, reportante del servidor y creación idempotente | test_incidents.py, test_incident_views.py, smoke_incidents_http.py |
| RF-024 | Atención correctiva | Toma exclusiva, notas internas, liberación con motivo/resumen, cierre diferenciado, no reparable con permiso y motivo | Tests de dominio, vistas y seis carreras PostgreSQL |
| RF-025 | Historial integrado por equipo | Ficha con auditoría, preventivos por ejecución e incidencias; paginación independiente y alcance docente propio | test_incident_views.py, test_incident_integration.py |
| Infraestructura | Django + PostgreSQL y monolito | Migraciones reproducibles, check, lint y tests reales | `docs/PRUEBAS.md` |
| Concurrencia de esta entrega | Ediciones y último administrador | Dos conexiones no sobrescriben cambios ni eliminan ambos administradores | `tests/test_concurrency.py` |

RF-001 a RF-025 tienen implementación y evidencia funcional local según alcance de cada
fila; ello no equivale a validación institucional ni despliegue. El dashboard incorpora
pendientes/en atención/cerradas y equipos con al menos dos reportes válidos en período,
sin productividad individual. Continúan pendientes revisión visual/física, CI remoto,
HTTPS institucional y activación de tarea horaria. HTTPS local con control de login y
restauración de backup ya verificados en fase 11; ver PILOTO.md. Cierres sin reversión en MVP.

| Preparación fase 11 | Criterio | Evidencia |
| --- | --- | --- |
| QA integral | Regresión PostgreSQL/JS, flujos completos HTTP y HTTPS con tres roles | 428 Django + 21 JS, smokes y PRUEBAS.md |
| Seguridad de respuesta | CSP, cámara del origen, no-store y restauración HTMX | test_pilot_security.py, smoke HTTPS |
| HTML estructural | IDs únicos, etiquetas/idioma/viewport en diez rutas | test_pilot_html.py; visual pendiente |
| Operación | WSGI, TLS, login 429, PG runtime restringido, preflight readonly | check_pilot, configure_proxy, serve_pilot, smoke_pilot_http |
| Recuperación | Snapshot, backup/media e integridad; restauración temporal sin tocar fuente | 28 tablas/1 archivo y test_pilot_backup.py |
| Aceptación final | Navegador/móvil, cámara, impresión, host autorizado y operación institucional | Procedimiento en PILOTO.md, pendiente de ejecución real |
