# Bitacora

Monolito modular para gestión de equipos y mantenimiento de laboratorios. Esta entrega
implementa **usuarios, roles, ubicaciones, dispositivos, movimientos, QR, etiquetas y escáner**.
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

El tercer incremento reutiliza `apps/assets` y la identidad UUID existente: QR PNG,
etiquetas individuales/por selección y escáner de cámara/imagen con búsqueda manual.
Antes de modificar se verificaron 116 pruebas. La suite tiene **145 pruebas Django**
aprobadas en PostgreSQL y **21 pruebas JavaScript**; detalles en `docs/PRUEBAS.md`.

## Entorno verificado

Python 3.12.13; Django 5.2.19; PostgreSQL 18; psycopg 3.3.8; django-htmx 1.29.0;
Bootstrap 5.3.8; HTMX 2.0.11; qrcode 8.2; Pillow 12.3.0; html5-qrcode 2.3.8;
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
```

Para detener el servidor use Ctrl+C. Para detener únicamente el clúster aislado:

```powershell
.\.venv\Scripts\python.exe scripts/local_database.py stop
```

## Documentación y límites

- [Arquitectura](docs/ARQUITECTURA.md), [modelo de datos](docs/MODELO_DATOS.md), [decisiones](docs/DECISIONES.md).
- [Reglas](docs/REGLAS_NEGOCIO.md), [requisitos](docs/REQUERIMIENTOS.md), [manual](docs/MANUAL.md).
- [Pruebas](docs/PRUEBAS.md), [seguridad](docs/SEGURIDAD.md), [avance](docs/AVANCE.md).

Pendientes: inspección visual real en escritorio/móvil, despliegue HTTPS, limitación
de intentos de login en el proxy y prueba de restauración de backups. No se implementaron
mantenimientos, incidencias, notificaciones ni reportes. Los traslados no dependen
de esos módulos. Advertencias de mantenimiento pendiente se integrarán cuando exista
ese módulo, sin inventar estados o resultados ahora.
Quedan pendientes cámara física, lectura móvil y una impresión real de etiquetas.
