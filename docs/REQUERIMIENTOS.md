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
| RF-010 (parcial) | Primer vencimiento por equipo | Meses calendario, fin de mes, bisiestos, valores inválidos | CalendarTests y creación periódica |
| RF-011 (parcial) | Primera ejecución con copias | Pendiente, sin finalizar, tareas limpias; editar no modifica copias | Creación/edición y retención |
| RF-019 (preventivos parcial) | Auditoría de configuración | Actor/fecha/cambios, inmutabilidad y rollback | test_maintenance.py |
| RF-019 (parcial) | Auditoría de usuarios, ubicaciones, categorías y equipos | Actor/fecha y cambios atómicos, eventos no editables y relaciones PROTECT | Pruebas de rollback, retención y eventos |
| Infraestructura | Django + PostgreSQL y monolito | Migraciones reproducibles, check, lint y tests reales | `docs/PRUEBAS.md` |
| Concurrencia de esta entrega | Ediciones y último administrador | Dos conexiones no sobrescriben cambios ni eliminan ambos administradores | `tests/test_concurrency.py` |

Pendientes: RF-010 desde la fecha real de cada cierre, RF-011 ciclos siguientes,
RF-012 a RF-018, RF-020 a RF-025 y auditoría operativa/incidencias. Los filtros de esta
entrega no constituyen el módulo de dashboard/reportes RF-022.
