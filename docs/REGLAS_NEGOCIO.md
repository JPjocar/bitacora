# Reglas implementadas

| Operación | Administrador | Técnico | Docente |
| --- | --- | --- | --- |
| Ingresar, salir, consultar su perfil, cambiar su contraseña | Sí | Sí | Sí |
| Consultar/crear/editar/desactivar/reactivar usuarios | Sí | No | No |
| Asignar uno de los tres roles y consultar permisos | Sí | No | No |
| Restablecer contraseña de otra cuenta de negocio | Sí | No | No |
| Consultar ubicaciones | Sí | Sí | No |
| Crear/editar/desactivar/reactivar ubicaciones | Sí | No | No |
| Consultar auditoría de cuentas y ubicaciones | Sí | No | No |
| Eliminar físicamente registros o modificar eventos | No | No | No |

Las comprobaciones se basan en permisos Django, no solo en nombres de grupos o botones.
Anónimos: redirección a login; autenticados sin permiso: 403, también en HTMX.
Cada cuenta solo consulta su perfil en `/cuentas/perfil/`, sin un ID modificable.

Un administrador no puede desactivarse ni cambiar su propio rol. No se puede retirar
el último administrador de negocio activo, ni siquiera con dos peticiones concurrentes.
El superusuario técnico se crea explícitamente por consola y no puede ser modificado
desde la gestión de usuarios. No se permite elevar `is_staff`/`is_superuser` desde formularios
o datos extra enviados a los servicios.

Contraseña inicial obligatoria, confirmada y validada (mínimo 12 caracteres, sin valores
comunes, solo numéricos o similares a los datos personales). Hashing nativo Django.
El cambio personal exige la contraseña actual y conserva la sesión actual. Restablecer
la contraseña invalida sesiones anteriores. Desactivar impide autenticación y acceso
en solicitudes posteriores. Reactivar es una edición autorizada y auditada.

Los roles son una política fija: no hay editor arbitrario de permisos. `sync_roles`
sincroniza la matriz de esta entrega y es idempotente. Su ejecución debe formar parte
del despliegue y coordinarse con cambios de permisos de futuros módulos.

Ubicación: nombre y tipo obligatorios, código opcional. Se impiden nombres/códigos
duplicados ignorando mayúsculas y espacios periféricos. Desactivar conserva todos los
eventos; reactivar no crea una entidad nueva. Actualmente se permite desactivar cualquier
ubicación porque aún no existe el módulo de equipos. No se simulan restricciones futuras.

Los formularios llevan versión del registro. Guardar una versión antigua muestra un
error y obliga a recargar; no sobrescribe cambios ajenos. Un guardado sin cambios no
crea eventos adicionales. Un reenvío de edición ya aplicada se rechaza por versión.
Las altas duplicadas se rechazan por unicidad; no se crean dos registros iguales.

GET/HEAD no modifican datos de negocio. Escrituras por POST con CSRF y patrón
POST–Redirect–GET. HTMX se usa solo en filtros GET; sin JavaScript funcionan filtros
y formularios mediante navegación convencional. Sesión expirada en HTMX redirige la
página completa; errores de red/403 tienen mensajes en el frontend.
