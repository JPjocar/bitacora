# Requisitos y trazabilidad

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
| RF-020 (parcial) | Situación temporal visible | Vencido/hoy/próximo a 7 días/posterior derivados, filtros sin iniciar trabajo | test_recurrence_views.py; sin notificaciones materializadas |
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
| Infraestructura | Django + PostgreSQL y monolito | Migraciones reproducibles, check, lint y tests reales | `docs/PRUEBAS.md` |
| Concurrencia de esta entrega | Ediciones y último administrador | Dos conexiones no sobrescriben cambios ni eliminan ambos administradores | `tests/test_concurrency.py` |

Pendientes: notificaciones de RF-020/RF-021, RF-022 a RF-025 y auditoría de incidencias.
Los eventos RELEASED y RUN_CREATED están disponibles para futura integración idempotente.
El historial de esta entrega es preventivo, por mantenimiento/ejecución; no completa el
historial integrado de incidencias de RF-025 ni constituye dashboard/reportes.
