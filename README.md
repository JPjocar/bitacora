# Bitacora

Monolito modular para gestión de equipos y mantenimiento de laboratorios. Esta entrega
implementa **únicamente usuarios, roles y ubicaciones**, más la infraestructura que necesitan.
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

## Entorno verificado

Python 3.12.13; Django 5.2.19; PostgreSQL 18; psycopg 3.3.8; django-htmx 1.29.0;
Bootstrap 5.3.8; HTMX 2.0.11; Ruff 0.17.4. Dependencias completas fijadas en
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

## Comprobaciones

```powershell
.\.venv\Scripts\python.exe scripts/manage_local.py check
.\.venv\Scripts\python.exe scripts/manage_local.py makemigrations --check --dry-run
.\.venv\Scripts\python.exe scripts/manage_local.py test --noinput -v 2
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe scripts/manage_local.py collectstatic --noinput
$env:DJANGO_DEBUG = 'false'
.\.venv\Scripts\python.exe scripts/manage_local.py check --deploy --fail-level WARNING
Remove-Item Env:DJANGO_DEBUG
```

La suite crea y elimina `test_bitacora`. Las pruebas de concurrencia comprueban conexiones
PostgreSQL distintas y ejecutan dos transacciones reales; no admiten SQLite.
Los resultados y límites efectivos se encuentran en [docs/PRUEBAS.md](docs/PRUEBAS.md).
Se incluye un workflow de GitHub Actions; su ejecución remota está pendiente.

Con el servidor y los datos demo disponibles:

```powershell
.\.venv\Scripts\python.exe scripts/smoke_http.py --credentials-file .local/demo-credentials.txt
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
dispositivos, movimientos, QR, mantenimientos, incidencias, notificaciones ni reportes.
El siguiente incremento sugerido es dispositivos, únicamente cuando se solicite.
