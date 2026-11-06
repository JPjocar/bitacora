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
