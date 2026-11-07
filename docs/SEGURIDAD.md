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
No se confía globalmente en `X-Forwarded-Proto`. En el piloto verificado, Waitress escucha
en loopback y confía solo en esa cabecera desde 127.0.0.1; Nginx la sobrescribe y elimina
cabeceras no admitidas. No se habilita SECURE_PROXY_SSL_HEADER para cualquier origen.

No hay autorización para puesta en producción. Antes de un piloto en red:

1. Adaptar el WSGI/proxy ya comprobados al host autorizado. `runserver` sigue siendo solo desarrollo.
2. Crear usuario PostgreSQL con privilegios mínimos; no utilizar el superusuario del clúster local.
3. Revisar el límite del proxy comprobado (5 POST/min/IP, ráfaga 10, 429) para usuarios/NAT reales.
   No se afirma resistencia a fuerza bruta sin ese control. Evitar credenciales en logs.
4. Generar secretos nuevos, usar DEBUG=False, servir staticfiles tras collectstatic, verificar
   certificado/cookies/cabeceras y ejecutar check --deploy en ese entorno.
5. Cambiar contraseñas demo o desactivar esas cuentas y revisar acceso del personal autorizado.
6. Definir política institucional de retención de datos y auditoría; no hay certificación legal.

Backup/restauración comprobados localmente en fase 11 (cuenta de mantenimiento y clientes PG 18):

```text
python scripts/manage_local.py backup_pilot .local/backups/nuevo --pg-bin "C:\Program Files\PostgreSQL\18\bin"
python scripts/manage_local.py verify_pilot_backup .local/backups/nuevo --pg-bin "C:\Program Files\PostgreSQL\18\bin"
```

Ejecutar con variables PG y credenciales del entorno correcto. Proteger el dump como datos
privados. Verificar usuarios, ubicaciones y eventos restaurados en una BD separada antes de
considerar válido el respaldo. Fase 11 también respalda/restaura media, aunque el MVP no
tiene cargas de archivos. Use únicamente copias propias/custodiadas; un dump restaura DDL
y no debe ejecutarse como contenido de origen desconocido.

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
creación/inscripciones/copias/auditoría son atómicas. Django Admin continúa readonly.

Ejecución: permiso de toma para técnicos; operación del responsable o permiso administrativo
explícito con motivo. Fecha anterior requiere permiso separado y justificación. Formularios
deshabilitan la fecha del técnico y el dominio vuelve a validar toda fecha. IDs de equipos
se acotan a la ejecución; IDs de tareas deben corresponder exactamente al contexto.
No se permite progreso antes del inicio, después de cierre o sobre equipo finalizado.
POST exige CSRF y versión vigente. Campos de actor/estado inyectados no se usan.
Los datos de configuración copiada siguen protegidos; save solo admite columnas operativas
explícitas. Quien tiene shell/SQL continúa en la frontera de confianza documentada.
La reversión de completados/cierres queda bloqueada hasta diseñar un flujo correctivo.

Recurrencia: create_next_run recarga al actor y exige permiso específico. Inscripciones,
estado activo de equipos/plan, tipo periódico, tareas aplicables y motivo anticipado se
revalidan en servidor bajo bloqueos. Claves de equipos no pertenecientes al mantenimiento
se rechazan. Versión y predecesor evitan duplicación por reenvío o carrera; el índice de
una ejecución abierta impide también selecciones simultáneas disjuntas. La transacción
incluye todas las copias y el evento, sin cambios parciales al fallar auditoría.

El detalle y los eventos por ciclo se acotan al mantenimiento de la URL. Docente recibe
403 incluso por URL directa/HTMX. Consultar vencimientos/historial no crea trabajo. El
smoke con escritura requiere --confirm-demo y servidor local, usando cuentas sintéticas.

Notificaciones: requiere usuario activo con permiso de avisos y acceso al módulo fuente. Todas las
consultas y escrituras se acotan al receptor autenticado, incluido el administrador;
la lectura ajena responde 404. Sin URLs de retorno controladas por cliente: se derivan
de las FK. Lectura individual/masiva por POST con CSRF. GET no marca ni genera avisos.
Contenido escapado en plantillas; no se copian motivos privados ni notas al resumen.
El destinatario se selecciona por grupo, permisos y actividad al generar cada aviso.

Panel/CSV/impresión exigen assets.view_device y maintenance.view_maintenance mediante
recarga de usuario; docente recibe 403 por URL directa. Respuestas privadas no-store,
incluidos fragmentos y descargas. Validación estricta de filtros antes de consultar o
exportar; valores inválidos no provocan una descarga de todos los datos. CSV neutraliza
prefijos de fórmulas, incluso con espacio/control inicial, y limita filas. El HTML se
escapa y no confía en el valor de nombres/códigos como marcado. No hay escrituras de
estado operativo desde el panel. Activación del programador y permisos del .env son
responsabilidad del piloto, con el procedimiento en MANUAL.md.

Incidencias: reportante autenticado, equipo de la ruta verificado con visible_devices,
activo/no retirado revalidado bajo bloqueo; no se aceptan actor, responsable, estado o
cierre inyectados desde formulario. Docente solo accede a sus casos; 404 al cambiar ID
por un ajeno. Los filtros se aplican sobre ese conjunto y no muestran ubicaciones ajenas.
Privacidad se aplica también al historial de ficha y avisos antiguos de usuarios demovidos.
Un docente puede seguir su reporte de un equipo archivado, sin obtener acceso a su ficha
completa ni a casos ajenos.

Notas, motivos y resúmenes de liberación son internos. Docente recibe únicamente estados
y el resumen final destinado al reportante; se advierte al autor que ese resumen será
compartido. Texto escapado, tamaños acotados y sin adjuntos o marcado interpretado.
Consultas de detalle/lista, filtros HTMX y contador son GET sin mutaciones; acciones
exigen POST y CSRF, permiso y versión revalidados en servicio. Ni ocultar botones ni
conocer un ID/UUID concede autorización. Acción desconocida 404; método no admitido 405.

Toma exclusiva con bloqueo del padre y control de versión; liberación/cierre y sus avisos
son atómicos. NO_REPARABLE exige permiso específico y justificación. Admin override exige
motivo; por defecto no tiene permiso de toma. Registro idempotente con token UUID único
y firma normalizada, sin sustituir el control por objeto. Las incidencias cerradas y
reportes originales no tienen vía de edición/borrado en UI ni Admin. Nuevos reportes no
reescriben uno anterior. El cierre correctivo no ejecuta servicios preventivos ni altera
estado físico automáticamente. Tests verifican seis carreras reales y rollback de fallos.

Panel restringe datos/reportes correctivos por permiso completo de incidencias, incluso
para usuarios que sí tengan permisos del panel previo. Se conservan BOM, neutralización
de fórmulas, límite de filas, validación de filtros y no-store de las exportaciones.

Fase 11: CSP del origen bloquea scripts externos/eval, objetos y framing; permite imágenes
QR data/blob, workers y cámara del origen. Estilos inline se conservan por Bootstrap.
Permissions-Policy limita cámara a self y deshabilita micrófono/geolocalización. Pendiente
verificar cámara/Bootstrap bajo esa política en un navegador real; no se presume certificación.

No-store se aplica también a anónimos/login/sesiones vencidas. La respuesta HX-Redirect
conserva cookies/cabeceras originales. Vary incluye HX-Request y HX-History-Restore-Request;
restaurar el dashboard retorna documento completo. Pruebas reprodujeron los fallos previos
y comprobaron sus correcciones. Cookies Secure/HttpOnly, CSRF y permisos se verificaron por HTTPS.

Proxy conserva host canónico al redirigir, valida host de HTTPS y limita POST web/admin
usando IP de conexión, sin confiar en X-Forwarded-For aportado por cliente. Se observó 429
con IP falsificada. No se creó bloqueo de cuentas ni limitador Django en memoria.
Access log omite query/body/cookies. La cuenta PG runtime no es superusuario ni crea
roles/bases; preflight comprueba esto y la preparación de la aplicación sin escribir.

Backup consistente mediante snapshot compartido con pg_dump y manifiesto de integridad;
restauración solo en BD nueva con nombre generado y prefijo protegido, eliminada al terminar.
No acepta un destino existente ni usa restauración destructiva en la fuente. ZIP no puede
escapar de su carpeta nueva ni copiar symlinks. Se verificaron filas/constraints/secuencias
y media, sin volcar datos en logs. Backup/secretos requieren ACL/copia cifrada y permisos
separados de runtime. SQL de backup exige operadores autorizados; no es una ruta web.

La preparación local no instala servicios ni publica dominios. PILOTO.md distingue lo
probado de HTTPS institucional, ACL, tareas, revisión física y recuperación operativa pendientes.

Auditoría de dependencias del 7 de noviembre de 2026: pip-audit 2.10.1 aislado contra los
requirements fijados detectó avisos en Pillow 12.3.0; se actualizó a 13.0.0 tras confirmar
la corrección con el proyecto. La repetición completa (base explícita y extras) no devolvió
avisos para los 12 paquetes de piloto/13 de desarrollo, sin omitidos. OSV tampoco los devolvió
para Bootstrap/HTMX/html5-qrcode. No se usó --fix automático. Es una consulta de catálogos,
no un pentest/certificación ni garantía futura; repetirla antes de cada despliegue.
