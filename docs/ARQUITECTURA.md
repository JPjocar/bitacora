# Arquitectura

Una aplicación Django, un proceso web desplegable y una base PostgreSQL.
HTML generado por Django Templates; Bootstrap 5.3 y HTMX 2 se sirven localmente.
No hay SPA, API REST, colas, microservicios ni capa Repository.

| Componente | Responsabilidad |
| --- | --- |
| `config` | Entorno, rutas, middleware, WSGI/ASGI y seguridad |
| `apps.accounts` | Usuario extendido, autenticación, roles, servicios y eventos de cuentas |
| `apps.locations` | Ambientes, validación, servicios y eventos de ubicaciones |
| `apps.core` | Clases abstractas de conservación/auditoría, permisos y presentación compartida |
| `templates`, `static` | Interfaz en español, componentes Bootstrap y filtros HTMX |
| `tests` | Pruebas funcionales, de seguridad y transacciones concurrentes |

Flujo de escritura: vista autorizada → formulario → servicio → validación dentro de
`transaction.atomic` → modelo + evento. La auditoría se guarda en la misma transacción:
si falla, se revierte el cambio. La autenticación/sesiones siguen las APIs nativas Django.

Las ubicaciones dependen solo de la referencia al usuario y de helpers compartidos.
`accounts` no importa `locations` en su dominio; el comando de demostración integra ambos.
El aprovisionamiento de roles conoce explícitamente los permisos disponibles de esta entrega.
No hay señales para encadenar operaciones críticas.

Los cambios de cuentas bloquean la fila del grupo Administrador y luego la cuenta:
un bloqueo común serializa cambios de roles y protege la existencia de un administrador
activo. Es adecuado para la administración de cuentas de un piloto pequeño. Los cambios
de ubicación bloquean solo la ubicación. Ambos usan `version` para rechazar formularios viejos.

Los modelos concretos se administran desde las pantallas del producto. Django Admin es
de solo lectura y no registra Group para evitar escrituras que salteen los servicios.
El operador con acceso a shell/SQL tiene una frontera de confianza mayor; véase seguridad.

Las dependencias QR, gráficos y otros módulos se incorporarán cuando se soliciten.
