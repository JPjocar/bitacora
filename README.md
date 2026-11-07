# Bitacora

Monolito modular para gestión de equipos y mantenimiento de laboratorios. Esta entrega
implementa **usuarios, roles, ubicaciones, dispositivos, movimientos, QR, etiquetas,
escáner, configuración, ejecución y recurrencia de mantenimientos preventivos,
notificaciones internas, dashboard, reportes básicos e incidencias con atención correctiva**.
Piloto académico con datos sintéticos; no representa un despliegue institucional autorizado.

## Estado inicial y alcance

La carpeta original contenía solamente `Prompt_Maestro_Codex_Bitacora.txt` (1.145 líneas),
leído íntegramente antes de programar. No existían proyecto, Git, modelos, migraciones,
servicios, permisos ni dependencias. El prompt permanece sin modificaciones.

- Autenticación, cierre de sesión por POST, perfil y cambio de contraseña.
- Alta, listado, búsqueda, edición, rol, desactivación/reactivación y restablecimiento de cuentas.
- Roles fijos Administrador, Técnico y Docente sobre Groups/Permissions de Django.
- Ubicaciones: listado, detalle, filtros, paginación, alta, edición y desactivación/reactivación.
- Historial protegido, servicios transaccionales, control de versiones y permisos en servidor.
- Bootstrap local, formularios accesibles y filtros HTMX con alternativa HTML convencional.
- Categorías, ficha de dispositivos con serie opcional, código único generado e inmutable,
  búsqueda manual, fechas y detalles técnicos opcionales, desactivación/reactivación.
- Consulta limitada para docentes; estado y observaciones operativas para técnicos.
- Traslados físicos con origen obtenido en servidor, destino activo, motivo, fecha efectiva,
  historial protegido y actualización atómica de ubicación. No equivalen a reparación.

El noveno incremento prepara el piloto: regresión de **428 pruebas Django y 21 JavaScript**,
corrección de restauración HTMX/caché de sesiones vencidas, cabeceras de protección,
WSGI con Waitress, proxy HTTPS con límite de login y backup/restauración verificados.
La auditoría detectó avisos en Pillow 12.3.0 y se actualizó a 13.0.0, con nueva regresión.
Sin cambios de modelos ni migraciones nuevas. Evidencia en `docs/PRUEBAS.md` y procedimiento
completo en [docs/PILOTO.md](docs/PILOTO.md). La revisión visual/física e instalación institucional
siguen pendientes; no se presenta esta preparación local como un despliegue oficial.

## Entorno verificado

Python 3.12.13; Django 5.2.19; PostgreSQL 18; psycopg 3.3.8; django-htmx 1.29.0;
Bootstrap 5.3.8; HTMX 2.0.11; qrcode 8.2; Pillow 13.0.0; html5-qrcode 2.3.8;
Ruff 0.17.4 y zxing-cpp 3.1.1 (solo pruebas). Dependencias completas fijadas en
`requirements.txt` y `requirements-dev.txt`. No se usa SQLite.

## Instalación reproducible (PowerShell)

Requisitos: Python 3.12 y PostgreSQL 18 instalados. No hace falta activar el entorno virtual:

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

En el entorno donde se realizó esta entrega, `py` no detectaba Python. Se utilizó el
Python 3.12.13 disponible en el runtime local para crear `.venv`; no se exige ese runtime
en otras instalaciones.

Elija **una** configuración de base de datos:

1. PostgreSQL existente: cree una BD y un usuario dedicado; copie `.env.example` a `.env`
   y configure su conexión, una clave secreta aleatoria y `DJANGO_DEBUG=true`.
   Para tests, el usuario de desarrollo necesita permiso `CREATEDB`.
2. Clúster de desarrollo aislado en Windows, usando binarios ya instalados:

```powershell
.\.venv\Scripts\python.exe scripts/local_database.py start
```

La segunda opción crea `.local/postgres`, genera `.env` sin sobrescribir uno existente,
usa autenticación SCRAM y escucha **solo en 127.0.0.1:55432**. No altera el servicio
PostgreSQL instalado en 5432. El usuario del clúster es superusuario **de PostgreSQL
de desarrollo**, nunca una cuenta web. No reutilice esta configuración en producción.
Se puede ajustar `--bin 'C:\Program Files\PostgreSQL\18\bin'`.

```powershell
.\.venv\Scripts\python.exe scripts/manage_local.py migrate
.\.venv\Scripts\python.exe scripts/manage_local.py sync_roles
.\.venv\Scripts\python.exe scripts/manage_local.py createsuperuser
.\.venv\Scripts\python.exe scripts/manage_local.py runserver 127.0.0.1:8000
```

Abra http://127.0.0.1:8000/. El superusuario se crea **interactivamente**; no hay contraseñas
fijas ni superusuarios automáticos. Ingrese por la interfaz principal y cree un usuario
con rol Administrador para el trabajo habitual. Django Admin queda como consulta interna;
las modificaciones de negocio deben pasar por los servicios.

`scripts/manage_local.py` es un lanzador exclusivo de desarrollo: lee entradas simples
`CLAVE=valor` de `.env` sin ejecutarlas y respeta variables ya definidas. No utiliza
expansión de variables ni comillas. En despliegue se inyectan variables de entorno
y se utiliza `python manage.py` directamente. No se cambia la política de PowerShell.

## Datos de demostración (opcional y explícito)

```powershell
.\.venv\Scripts\python.exe scripts/manage_local.py seed_demo --confirm-demo
```

Crea `demo_admin`, `demo_tecnico`, `demo_docente` y tres ambientes ficticios. Genera y
muestra contraseñas aleatorias una sola vez. Cámbielas desde **Mi perfil**. Exige
`DEBUG=True`; rechaza ejecuciones posteriores si ya existen cuentas demo y no cambia
sus credenciales. No crea superusuarios.

En esta entrega se ejecutó para la verificación HTTP; las credenciales temporales
quedaron en `.local/demo-credentials.txt`, ignorado por Git. No publique ese archivo.

Para agregar dos dispositivos y un traslado ficticios a esa demo:

```powershell
.\.venv\Scripts\python.exe scripts/manage_local.py seed_assets_demo --confirm-demo
```

Requiere la demo base y `sync_roles`. No restablece contraseñas ni modifica equipos
ya existentes con esos nombres. Las seis categorías iniciales se crean con migraciones.

Para agregar un preventivo único y otro periódico a esos equipos sintéticos:

```powershell
.\.venv\Scripts\python.exe scripts/manage_local.py seed_maintenance_demo --confirm-demo
```

Solo con DEBUG=True, demo de dispositivos y permisos sincronizados. Es idempotente y
conserva registros previos. Las ejecuciones quedan pendientes, sin trabajo acreditado.
La migración nueva es `maintenance/0001_initial`; ejecute migrate y sync_roles y reinicie
el servidor para cargar la app y las rutas nuevas.

Para actualizar a ejecución preventiva aplique también `maintenance/0002_execution_workflow`
y vuelva a ejecutar `sync_roles`. Conserva equipos, tareas y fechas de las ejecuciones
previas. Los técnicos reciben permisos de toma/ejecución; administradores, intervención
justificada y fecha anterior autorizada. Reinicie el servidor tras actualizar.

Para recurrencia aplique `maintenance/0003_recurring_runs`, ejecute `sync_roles` y reinicie.
Técnicos y administradores reciben `create_next_run`. Se habilita una sola ejecución
abierta por mantenimiento; debe cerrarla o cancelarla antes de abrir la siguiente.
Los vencimientos se derivan al consultar; no hay cron ni apertura automática.

## Actualizar desde una entrega anterior

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe scripts/manage_local.py migrate
.\.venv\Scripts\python.exe scripts/manage_local.py sync_roles
```

Reinicie el servidor para cargar `apps/assets` y sus rutas. Los roles existentes reciben
los nuevos permisos; no se recrean las cuentas. No hay migraciones destructivas.

Configure `BITACORA_PUBLIC_URL` en `.env` o el entorno **antes de imprimir**: por ejemplo
`http://127.0.0.1:8000` en desarrollo o el origen HTTPS estable del instituto en despliegue.
No incluye rutas, credenciales ni parámetros. El valor local predeterminado no sirve
desde otro teléfono: allí localhost apuntaría al propio teléfono. No se ha desplegado
HTTPS. Si cambia el dominio configurado, debe conservar el anterior mediante una
redirección controlada o volver a imprimir etiquetas. Véase el manual para escanear.

## Comprobaciones

```powershell
.\.venv\Scripts\python.exe scripts/manage_local.py check
.\.venv\Scripts\python.exe scripts/manage_local.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe scripts/manage_local.py test --noinput -v 2
node --test tests/js/*.test.cjs
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts/manage_local.py collectstatic --noinput
$env:DJANGO_DEBUG = 'false'
$env:BITACORA_PUBLIC_URL = 'https://bitacora.example.edu'
.\.venv\Scripts\python.exe scripts/manage_local.py check --deploy --fail-level WARNING
Remove-Item Env:DJANGO_DEBUG
Remove-Item Env:BITACORA_PUBLIC_URL
```

La suite crea y elimina `test_bitacora`. Las pruebas de concurrencia comprueban conexiones
PostgreSQL distintas y ejecutan dos transacciones reales; no admiten SQLite.
Los resultados y límites efectivos se encuentran en [docs/PRUEBAS.md](docs/PRUEBAS.md).
Se incluye un workflow de GitHub Actions; su ejecución remota está pendiente.
Node 22 o posterior se usa únicamente para las pruebas de JavaScript, sin npm ni bundler.
El dominio de ejemplo del check no constituye un despliegue ni una URL para imprimir.

Con el servidor y los datos demo disponibles:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_http.py --credentials-file .local/demo-credentials.txt
# Con seed_assets_demo también ejecutado:
.\.venv\Scripts\python.exe scripts/smoke_http.py --assets
# Incluye validación HTTP de QR, etiquetas y escáner:
.\.venv\Scripts\python.exe scripts/smoke_http.py --qr
# Con seed_maintenance_demo también ejecutado:
.\.venv\Scripts\python.exe scripts/smoke_http.py --qr --maintenance
# Flujo operativo HTTP; crea y conserva un preventivo SINTÉTICO con cierre parcial:
.\.venv\Scripts\python.exe scripts/smoke_execution_http.py --confirm-demo
# Dos ciclos periódicos, calendario e historial; conserva datos sintéticos:
.\.venv\Scripts\python.exe scripts/smoke_execution_http.py --confirm-demo --recurrence
# Materializar avisos (repetible) y verificar bandeja, panel y reportes:
.\.venv\Scripts\python.exe scripts/manage_local.py generate_notifications
.\.venv\Scripts\python.exe scripts/smoke_dashboard_http.py --confirm-demo
# Incidencias: crea y conserva tres reportes SINTÉTICOS con los tres resultados de cierre:
.\.venv\Scripts\python.exe scripts/smoke_incidents_http.py --confirm-demo
```

Para el piloto con DEBUG=False use `requirements-pilot.txt`, una cuenta PostgreSQL de
ejecución restringida y el proxy revisado; no publique runserver. Configuración y pasos:
[guía de piloto](docs/PILOTO.md). Los comandos de operación aceptan un entorno explícito:

```powershell
.\.venv\Scripts\python.exe scripts/manage_local.py --env-file .local/pilot.env check_pilot --allow-demo
.\.venv\Scripts\python.exe scripts/serve_pilot.py --env-file .local/pilot.env --allow-demo
# Backup con la cuenta de mantenimiento, nunca sobrescribe la base fuente:
.\.venv\Scripts\python.exe scripts/manage_local.py backup_pilot .local/backups/nuevo --pg-bin 'C:\Program Files\PostgreSQL\18\bin'
.\.venv\Scripts\python.exe scripts/manage_local.py verify_pilot_backup .local/backups/nuevo --pg-bin 'C:\Program Files\PostgreSQL\18\bin'
```

Para detener el servidor use Ctrl+C. Para detener únicamente el clúster aislado:

```powershell
.\.venv\Scripts\python.exe scripts/local_database.py stop
```

## Documentación y límites

- [Arquitectura](docs/ARQUITECTURA.md), [modelo de datos](docs/MODELO_DATOS.md), [decisiones](docs/DECISIONES.md).
- [Reglas](docs/REGLAS_NEGOCIO.md), [requisitos](docs/REQUERIMIENTOS.md), [manual](docs/MANUAL.md).
- [Pruebas](docs/PRUEBAS.md), [seguridad](docs/SEGURIDAD.md), [avance](docs/AVANCE.md).
- [Preparación, operación y recuperación del piloto](docs/PILOTO.md).

Pendientes: inspección visual real en escritorio/móvil y pruebas físicas, dominio/certificado
institucional, ACL y despliegue autorizado, arranque/tareas y CI remoto. HTTPS local, límite
de login y restauración de backup sí fueron comprobados; ver límites en PILOTO.md.
Active la tarea periódica de avisos según `docs/MANUAL.md`; sin ella los
avisos de fecha no se actualizan. El cierre o fecha real de un equipo completado
no se revierte en este MVP; tampoco se reabren incidencias cerradas. El siguiente paso
recomendado es aceptación visual/física y operación en el equipo autorizado. Los traslados
conservan los resultados preventivos. Los ciclos siguientes se crean manualmente.
Quedan pendientes cámara física, lectura móvil y una impresión real de etiquetas.
