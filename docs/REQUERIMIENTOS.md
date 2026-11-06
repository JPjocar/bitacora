# Requisitos y trazabilidad

| RF | Alcance entregado | Criterio de aceptación | Evidencia |
| --- | --- | --- | --- |
| RF-001 | Login/logout, perfil, cuentas y roles | Sin permisos no se ejecuta operación; roles reales, sesión y contraseñas protegidas | `tests/test_accounts.py`, `tests/test_security.py` |
| RF-002 | Ubicaciones y desactivación | Nombre/tipo válidos, unicidad, consulta y actualización autorizadas; historial conservado | `tests/test_locations.py` |
| RF-003 | Categorías y dispositivos | Ficha con serie/detalles opcionales y roles; archivo sin borrado | `tests/test_assets.py`, `tests/test_asset_views.py` |
| RF-004 | Código único y búsqueda manual | Generación criptográfica, colisión reintentada, identidad inmutable, búsqueda sin distinguir caja/espacios | Pruebas de colisión, inmutabilidad y filtros |
| RF-005 | Traslado transaccional | Origen vigente, destino válido, historial y ubicación atómicos; sin sobrescritura concurrente | `tests/test_movements.py`, `tests/test_asset_concurrency.py` |
| RF-019 (parcial) | Auditoría de usuarios, ubicaciones, categorías y equipos | Actor/fecha y cambios atómicos, eventos no editables y relaciones PROTECT | Pruebas de rollback, retención y eventos |
| Infraestructura | Django + PostgreSQL y monolito | Migraciones reproducibles, check, lint y tests reales | `docs/PRUEBAS.md` |
| Concurrencia de esta entrega | Ediciones y último administrador | Dos conexiones no sobrescriben cambios ni eliminan ambos administradores | `tests/test_concurrency.py` |

RF-006 a RF-018 y RF-020 a RF-025 no implementados. La auditoría de mantenimiento
e incidencias de RF-019 tampoco se implementó. Los filtros de este incremento
no constituyen el módulo de dashboard/reportes RF-022.
