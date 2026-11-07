# Piloto local y preparación operativa — 7 de noviembre de 2026 (Lima)

La fase 11 del maestro prepara una demostración reproducible. No hay publicación
institucional, DNS público ni servicio del sistema instalado. Los módulos están
implementados; la evidencia local está en PRUEBAS.md. Se mantienen datos sintéticos.

## Configuración verificada

Python 3.12.13, Django 5.2.19, PostgreSQL 18.4, Waitress 3.0.2 y Nginx/Windows 1.31.8.
Waitress es la única dependencia Python añadida, separada en requirements-pilot.txt.
Pillow se actualizó de 12.3.0 a 13.0.0 por avisos de seguridad confirmados en su proyecto;
la compatibilidad y QR se revalidaron con Python 3.12. No se usó una actualización automática --fix.
Nginx y OpenSSL son herramientas de infraestructura, no librerías de la aplicación.
Se auditó Python con pip-audit 2.10.1 en un entorno aislado: inicialmente detectó avisos
para Pillow 12.3.0. Después de corregirlo, 12 paquetes del piloto y 13 de desarrollo,
sin paquetes omitidos, no presentaron avisos conocidos. Las tres bibliotecas frontend
tampoco los presentaron en OSV en la consulta del 7 de noviembre de 2026. Repetir antes
de desplegar; el catálogo no garantiza ausencia de fallos ni sustituye pruebas de seguridad.
OpenSSL 3.5.6 generó un certificado autofirmado de siete días con SAN localhost/127.0.0.1.
Los clientes HTTPS verifican ese certificado con su CA explícita; no se desactiva TLS.

Nginx escucha solo en 127.0.0.1:8088/8443; Waitress solo en 127.0.0.1:8081.
HTTP redirige a un origen fijo HTTPS, sin confiar en Host para construir la redirección.
El proxy sirve staticfiles, impide listar directorios y no publica media. Sobrescribe
X-Forwarded-Proto/For y elimina otras cabeceras de proxy. Waitress confía únicamente
en X-Forwarded-Proto desde el proxy local; no se configura confianza global en Django.

POST de login web y Django Admin comparten límite por IP real: 5/minuto, ráfaga 10;
exceso responde 429 y Retry-After: 60. GET no consume el límite. No hay bloqueo de cuenta
ni limitador en memoria de Django. Ajustar tras medir usuarios simultáneos/NAT del piloto.
El acceso directo al WSGI queda confinado al host; el equipo servidor debe ser administrado
por personal autorizado. No abrir 8081 al exterior ni confiar en cabeceras de clientes.

## Instalación y cuenta de ejecución

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-pilot.txt
# Con la cuenta de migración/propietaria configurada en el entorno:
.\.venv\Scripts\python.exe scripts/manage_local.py migrate --noinput
.\.venv\Scripts\python.exe scripts/manage_local.py sync_roles
.\.venv\Scripts\python.exe scripts/manage_local.py collectstatic --noinput
```

Use una cuenta propietaria para migraciones y otra PostgreSQL de ejecución sin
SUPERUSER/CREATEDB/CREATEROLE. `deploy/postgres_runtime.sql` contiene concesiones mínimas
para este esquema; adapte el nombre de base/rol y ejecute como propietario. Establezca
contraseña generada mediante `\password`, sin ponerla en argumentos ni versionarla.
Las concesiones por defecto se aplican como el propietario de futuras tablas/secuencias.
La cuenta de backup/verificación sí necesita lectura/exportar snapshot y CREATEDB para
la restauración temporal; no se usa esa cuenta para servir la aplicación.

Use `deploy/pilot.env.example` como referencia para un archivo privado **fuera de Git**;
reemplace todos los marcadores y configure origen, hosts y CSRF coherentes. Secret key
aleatoria de al menos 50 caracteres. Variables ya exportadas tienen prioridad sobre el
archivo. `serve_pilot.py` no lee el .env de desarrollo de forma automática.

En esta prueba se generó `.local/pilot.env` con secretos aleatorios y un rol runtime
restringido, sin mostrarlos en consola. Exclusión de Git **no es control de acceso**:
en el equipo piloto configure ACL NTFS para la cuenta de servicio/administración y
proteja también claves TLS y backups. No reutilice el superusuario PostgreSQL del clúster
aislado como runtime. Las cuentas web demo tienen contraseñas aleatorias preexistentes.

```powershell
.\.venv\Scripts\python.exe scripts/manage_local.py --env-file .local/pilot.env check_pilot --allow-demo
.\.venv\Scripts\python.exe scripts/serve_pilot.py --env-file .local/pilot.env --allow-demo
```

`check_pilot` no escribe: exige DEBUG=False, check --deploy sin advertencias, origen HTTPS
autorizado/CSRF, migraciones aplicadas, matriz exacta de roles, administrador activo,
estáticos recolectados y rol PostgreSQL restringido. Sin --allow-demo rechaza cuentas
demo activas. Use esa excepción solo para demostración sintética controlada; cree primero
un administrador propio antes de desactivar demo_admin para conservar la última administración.

## Proxy y TLS

Descargue Nginx de su sitio oficial y conserve la versión/hash evaluados. No se añadió
al repositorio ningún binario ni certificado. Registro local del ZIP 1.31.8:
`FBB1501009BE34655CC238D460714CF20391B639013F4C73859813D7938783FD` (SHA-256).
Es un registro de la descarga HTTPS, no una afirmación de verificación PGP independiente.
La distribución Windows es beta según su documentación; para exposición real evalúe
un proxy administrado en Linux y haga pruebas de capacidad. Aquí solo se validó el piloto local.

Con certificado y clave propios existentes, renderice un archivo nuevo:

```powershell
.\.venv\Scripts\python.exe scripts/configure_proxy.py --host localhost --certificate .local/certs/localhost.crt --key .local/certs/localhost.key --mime-types .local/tools/nginx-1.31.8/conf/mime.types --output .local/nginx-reviewed.conf
$pilotNginx = (Resolve-Path .local/tools/nginx-1.31.8/nginx.exe).Path
$pilotPrefix = (Resolve-Path .local/tools/nginx-1.31.8).Path.Replace('\','/') + '/'
$pilotConfig = (Resolve-Path .local/nginx-reviewed.conf).Path.Replace('\','/')
& $pilotNginx -p $pilotPrefix -c $pilotConfig -t
# Solo tras nginx -t correcto, proceso local oculto; no instala un servicio:
Start-Process -FilePath $pilotNginx -ArgumentList @('-p',$pilotPrefix,'-c',$pilotConfig) -WindowStyle Hidden
# Parada ordenada del proxy propio:
& $pilotNginx -p $pilotPrefix -c $pilotConfig -s quit
```

El renderer rechaza rutas/host con inyección, puertos repetidos y sobrescritura de una
configuración ya existente. Guarde los valores del proceso propio; no detenga servicios
ajenos. En esta sesión se usó `.local/nginx-pilot-v2.conf`; la primera validación detectó
map_hash_bucket_size insuficiente y se corrigió a 64 antes de iniciar el proxy.
El certificado local no es un certificado público ni permite validar cámara en otro móvil.

## Verificación HTTPS e integral

Ejecute los smokes desde el entorno QA que incluye requirements-dev.txt (ZXing independiente
para decodificar el QR) además de requirements-pilot.txt. El servidor no requiere ZXing/Ruff.

```powershell
.\.venv\Scripts\python.exe scripts/smoke_pilot_http.py --ca-file .local/certs/localhost.crt --confirm-demo
# Flujos de escritura contra WSGI/DEBUG=False y rol runtime restringido:
$env:SSL_CERT_FILE = (Resolve-Path .local/certs/localhost.crt).Path
.\.venv\Scripts\python.exe scripts/smoke_execution_http.py --base-url https://localhost:8443 --confirm-demo --recurrence
.\.venv\Scripts\python.exe scripts/smoke_incidents_http.py --base-url https://localhost:8443 --confirm-demo
Remove-Item Env:SSL_CERT_FILE
```

Los smokes son locales y sintéticos; los de ejecución/incidencias conservan nuevos
registros como evidencia. El smoke HTTPS genera intentos fallidos al final para comprobar
429. Espere la recuperación del límite antes de repetir logins; no lo desactive para uso
real. Al operar por HTTPS, los clientes envían Origin/Referer como un navegador y conservan
CSRF: no se relajó la protección para hacer pasar las pruebas.

## Backup y restauración probada

```powershell
# Cuenta de mantenimiento/backup con acceso al clúster; directorio nuevo y privado:
.\.venv\Scripts\python.exe scripts/manage_local.py backup_pilot .local/backups/mi-backup --pg-bin 'C:\Program Files\PostgreSQL\18\bin'
.\.venv\Scripts\python.exe scripts/manage_local.py verify_pilot_backup .local/backups/mi-backup --pg-bin 'C:\Program Files\PostgreSQL\18\bin'
```

Se crea database.dump (pg_dump custom, sin propietario/ACL), media.zip y manifest.json.
Dump y huellas de las tablas comparten un snapshot PostgreSQL exportado. Media se copia
aparte y se detectan cambios; este MVP no tiene cargas de archivos. Para futuras cargas,
detenga escrituras durante la copia conjunta. Use clientes de la misma versión mayor
del servidor. No se sobrescribe un directorio existente ni se respalda dentro de media.
Se rechazan enlaces simbólicos y junctions Windows para no copiar destinos externos.

Verificar comprueba hashes, crea **solo** una BD aleatoria `bitacora_verify_<hex>`, restaura
con --exit-on-error/--single-transaction, compara todas las filas, comprueba restricciones
y secuencias y recupera media en una carpeta nueva verificada. No acepta un nombre de
destino del usuario ni usa --clean/--create. Al terminar elimina únicamente su BD temporal.
La media recuperada queda en `verification-media-<uuid>` dentro del backup para inspección.
Si falla, no se considera válido el backup; revise el error antes de reintentar en otra carpeta.

Resultado observado: **28 tablas iguales, restricciones y secuencias correctas y un archivo
media sintético restaurado**. Los backups contienen usuarios, hashes de contraseña y
sesiones: restrinja ACL, cifre la copia externa y manténgala fuera del servidor/repositorio.
SHA-256 detecta corrupción; no sustituye cifrado ni autenticación del origen del backup.
Solo se verifican/restauran copias propias y custodiadas: el dump contiene DDL ejecutable,
por lo que no se utiliza esta herramienta con archivos de origen desconocido.
No se respaldan roles globales, certificados o .env: custódielos por separado.

Recuperación operativa: detenga escrituras, conserve la base original, cree una base
nueva con la cuenta propietaria y restaure allí el dump verificado; recupere la media en
una instalación nueva y reaplique las concesiones del rol runtime. Configure PGDATABASE
para esa base y ejecute checks/smokes antes de conmutar el servicio. Esta conmutación a
una instalación real no se ejecutó. Nunca sustituya la fuente usando el comando de verificación.

Frecuencia inicial propuesta para el piloto: copia diaria y antes de migraciones;
conservar siete diarias y cuatro semanales, con copia cifrada fuera del host. Objetivos
propuestos, aún sin medir: RPO 24 h y RTO 2 h. Validar responsables/capacidad y medir una
recuperación en el equipo real antes de aprobar esos objetivos. No se instaló tarea de backup.

## Avisos, mantenimiento y registro de incidencias del piloto

Tarea horaria ya descrita en MANUAL.md, ahora con la cuenta/runtime del piloto:
`scripts/manage_local.py --env-file .local/pilot.env generate_notifications`.
No poner secretos en argumentos; configurar carpeta de trabajo, ejecución sin solapar,
registro del código de salida y revisión de errores. Se ejecutó manualmente: 4 nuevos,
luego 0. El Programador de tareas aún no está instalado/configurado por esta entrega.

Access log del proxy omite query strings, cuerpos y cookies; error logs se restringen
al personal técnico. Rotar logs y respaldos según política acordada. Django no imprime
contraseñas en sus eventos y las herramientas de backup no vuelcan errores con filas.
Consultar contador de 429, errores 5xx y fallo de tareas; no medir productividad de técnicos.

## Aceptación pendiente en el equipo real

No hubo navegador conectado. Antes de usarlo con personas, verificar y registrar:

1. Escritorio ~1366 px y móvil ~390 px: login, menú, teclado/foco, contraste, formularios
   inválidos, tablas sin desbordamiento global, vacíos y estados de error.
2. Filtros HTMX, Atrás/restauración, sesión vencida, contador a 30 s, sin conexión y uso
   sin JavaScript. CSP/cámara en un navegador real, no solo respuestas HTTP.
3. Flujo técnico preventivo y correctivo; docente solo ve sus casos; pruebas de doble
   toma simultánea en dos sesiones y conservación del historial.
4. QR en cámara/archivo/móvil con HTTPS confiable, permiso denegado y etiqueta impresa
   físicamente. Impresión HTML con saltos/columnas legibles.
5. Host/usuarios/certificado institucional autorizados, ACL, firewall, cuenta runtime,
   arranque automático del servicio, tareas, restauración cronometrada y copia externa.

No se simularon capturas ni aceptación institucional. GitHub Actions se amplió para
instalar clientes PostgreSQL 18 y verificar recuperación, pero no se ejecutó remotamente.

## Fuentes oficiales utilizadas

- [Waitress: argumentos y proxy confiable](https://docs.pylonsproject.org/projects/waitress/en/latest/arguments.html).
- [Nginx: Windows y limitaciones](https://nginx.org/en/docs/windows.html), [limit_req](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html).
- [PostgreSQL 18: pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html), [pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html).
- [PostgreSQL: clientes y repositorio Ubuntu](https://www.postgresql.org/download/linux/ubuntu/).
- [Django 5.2: checklist de despliegue](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).
- [PyPA pip-audit](https://github.com/pypa/pip-audit) y [API OSV](https://google.github.io/osv.dev/api/).
- [Pillow 13.0.0](https://pillow.readthedocs.io/en/stable/releasenotes/13.0.0.html) y
  [aviso del proyecto Pillow](https://github.com/python-pillow/Pillow/security/advisories/GHSA-78g4-xqwv-q3g8).
