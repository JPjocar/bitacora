# Seguridad y operación

Controles implementados: permisos en vistas y servicios, recarga del actor para no
confiar en cachés de permisos obsoletas, sesiones Django, CSRF, escaping HTML, validadores
de contraseñas, operaciones POST, bloqueo de elevación de privilegios y referencias PROTECT.
Las páginas autenticadas llevan `Cache-Control: private, no-store`; HTMX no guarda
contenido privado en su caché de historial ni evalúa scripts de fragmentos.

Auditoría transaccional explícita sin contraseñas, hashes, tokens o cookies. Conserva datos
de cuenta modificados (nombre/correo) solo cuando existen; su lectura se limita a administradores.
Los eventos no se actualizan/eliminan por las APIs ORM expuestas. El operador SQL puede
eludir estas barreras: no es una bitácora criptográfica ni una certificación de inmutabilidad.

Configuración: secretos solo por entorno, `.env`/BD local/credenciales excluidos de Git,
DEBUG falso por defecto, HTTPS y cookies Secure cuando DEBUG=False, HSTS, nosniff,
X-Frame-Options DENY y zona America/Lima. Configure hosts y orígenes CSRF del dominio real.
No se confía automáticamente en `X-Forwarded-Proto`; un proxy debe configurarse y verificarse
antes de habilitar una cabecera de proxy confiable.

No hay autorización para puesta en producción. Antes de un piloto en red:

1. Configurar servidor WSGI/ASGI de producción y proxy HTTPS. `runserver` es solo desarrollo.
2. Crear usuario PostgreSQL con privilegios mínimos; no utilizar el superusuario del clúster local.
3. Configurar limitación de intentos de login en el proxy (Django Auth no la incorpora).
   No se afirma resistencia a fuerza bruta sin ese control. Evitar credenciales en logs.
4. Generar secretos nuevos, usar DEBUG=False, servir staticfiles tras collectstatic, verificar
   certificado/cookies/cabeceras y ejecutar check --deploy en ese entorno.
5. Cambiar contraseñas demo o desactivar esas cuentas y revisar acceso del personal autorizado.
6. Definir política institucional de retención de datos y auditoría; no hay certificación legal.

Backups de PostgreSQL (procedimiento propuesto, restauración todavía no ejecutada):

```text
pg_dump --format=custom --file=bitacora.dump --dbname=bitacora
createdb bitacora_restore
pg_restore --exit-on-error --no-owner --dbname=bitacora_restore bitacora.dump
```

Ejecutar con variables PG y credenciales del entorno correcto. Proteger el dump como datos
privados. Verificar usuarios, ubicaciones y eventos restaurados en una BD separada antes de
considerar válido el respaldo. Este incremento no maneja archivos media.

Las herramientas de consola y SQL son acceso de confianza: no usar `QuerySet.update`,
ediciones directas de grupos o `save()` aislados para operaciones de negocio. Invocar
los servicios para preservar reglas/auditoría. La recuperación técnica de superusuarios
mediante comandos internos no genera eventos de negocio y debe registrarse operativamente.

En dispositivos el UUID/código no autoriza acceso. La consulta docente restringe objetos
tanto en listados como por URL directa, y omite datos técnicos/internos. El formulario
operativo del técnico no acepta cambio de ficha o ubicación. El origen de un movimiento,
su autor y su fecha registrada se obtienen en servidor. Las confirmaciones de advertencia
se vuelven a comprobar bajo bloqueo del equipo. El historial usa FKs PROTECT.

La integración preventiva consulta si hay ejecución pendiente y exige confirmar el aviso.
No se afirma haber probado traslados durante trabajo preventivo en ejecución: las acciones
de toma/inicio/avance/cierre pertenecen a la fase posterior.

QR: `BITACORA_PUBLIC_URL` fija el origen, independiente del encabezado Host. En producción
debe ser HTTPS; `check --deploy` lo exige. Mantenga estable el dominio y configure también
ALLOWED_HOSTS/CSRF_TRUSTED_ORIGINS y el proxy según el despliegue. Los PNG y etiquetas
requieren autenticación y llevan Cache-Control privado/no-store igual que las fichas.
Las imágenes impresas no contienen secretos y no sustituyen la autenticación.

El escáner no navega al texto decodificado ni hace peticiones a ese origen. Lo envía
por POST/CSRF al servidor propio, que valida origen, ruta exacta y visibilidad. Rechaza
credenciales, parámetros, fragmentos, rutas codificadas/administrativas y URLs externas.
Las imágenes elegidas (PNG/JPEG/WebP, hasta 10 MB) se leen localmente; no hay upload.
Al cerrar el modal, ocultar la página o navegar se solicita detener la cámara y se
descartan callbacks antiguos. La prueba física de permisos/HTTPS/cámara está pendiente.

Preventivos: permisos en vistas y servicios, recarga del actor para descartar permisos
obsoletos. Estado, actor y copias se generan en servidor. Formsets con tamaño limitado;
el dominio revalida equipos, categorías, tareas y fechas. Agregar filas también exige
CSRF. La clave de envío deduplica, no autoriza. Bloqueos y versión protegen ediciones;
creación/inscripciones/copias/auditoría son atómicas. No hay endpoints operativos ni
acceso Django Admin para marcar tareas o modificar ejecuciones directamente.
