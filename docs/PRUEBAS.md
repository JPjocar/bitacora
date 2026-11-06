# Verificación realizada

Fecha de la entrega: **5 de noviembre de 2026, America/Lima**.
Entorno local Windows, Python 3.12.13, PostgreSQL **18.4** real en 127.0.0.1:55432,
Django 5.2.19. Datos exclusivamente sintéticos. No se usó SQLite.

## Resultados

| Comprobación ejecutada | Resultado observado |
| --- | --- |
| `scripts/manage_local.py migrate --noinput` | Migraciones de Django y cuatro migraciones propias aplicadas |
| `scripts/manage_local.py sync_roles` | Tres grupos y matriz de permisos aprovisionados |
| `scripts/manage_local.py check` | 0 problemas |
| `scripts/manage_local.py makemigrations --check --dry-run` | No changes detected |
| `scripts/manage_local.py test --noinput -v 2` | **62 pruebas OK, 33,418 s**, base temporal creada/eliminada |
| `python -m ruff check .` | All checks passed |
| `python -m ruff format --check .` | 61 archivos Python con formato correcto |
| `python -m pip check` | No broken requirements found |
| `scripts/manage_local.py collectstatic --noinput` | 171 archivos estáticos copiados |
| `check --deploy --fail-level WARNING`, con `DJANGO_DEBUG=false` | 0 problemas |
| Arranque `runserver 127.0.0.1:8000 --noreload` | Servidor accesible por HTTP local |
| `scripts/smoke_http.py` | Login/logout, perfil y permisos de los tres roles, formularios, fragmentos HTMX y assets locales: correctos |
| `git check-ignore` sobre secretos y entorno | `.env`, `.venv` y `.local` excluidos |

El comando de tests completo queda en README. Salida detallada de esta ejecución:
`.local/tests-final.txt` (local, no versionado). Los resultados no dependen de ese log:
se pueden reproducir con la suite incluida. La primera ejecución tuvo 54 pruebas OK;
se ampliaron tras la revisión de seguridad hasta las 62 de la tabla.

## Cobertura funcional

`tests/test_accounts.py` (30 casos): matriz de roles/idempotencia, hash y validación de
contraseñas, rechazo de privilegios inyectados, usuario duplicado incluso con otra caja,
roles inválidos, permiso específico de asignación, actor desactivado con caché antigua,
edición/desactivación, protección propia y del último administrador, superusuarios
protegidos, conflicto de versión, no-op, rollback de auditoría, conservación del historial,
invalidez de sesiones tras reset, cambio personal, redirección segura del login,
logout POST, permisos por URL, formularios, CSRF, filtros HTMX y demo explícita.

`tests/test_locations.py` (21 casos): normalización, código opcional, unicidad en servidor
y BD, campos inválidos, desactivación/reactivación con historial, PROTECT, rechazo de
DELETE/edición de eventos, guardado sin cambios, versiones antiguas, rollback, matriz de
permisos, privacidad del historial, render de páginas, ID inexistente, métodos HTTP,
validaciones de formularios, versión requerida, CSRF, filtros/paginación/restauración
de historial HTMX, sesión expirada y escaping XSS.

`tests/test_security.py` (7 casos): acceso restringido a Django Admin, imposibilidad de
eludir servicios mediante el panel, sesión de cuenta desactivada, no-store, creación con
CSRF válido, redirección HTTPS y páginas de error con DEBUG=False.

`tests/test_concurrency.py` (4 TransactionTestCase):

1. Dos ediciones de una ubicación: una se guarda y la otra se rechaza por versión.
2. Dos ediciones de una cuenta: una se guarda; el historial no se duplica.
3. Dos degradaciones de administradores: se conserva uno activo.
4. Dos altas de ubicación con el mismo nombre/código: queda un solo registro.

Cada caso abre dos hilos con conexiones independientes, comprueba `pg_backend_pid()`
distintos, sincroniza el comienzo mediante barrera y usa timeout de bloqueo. Se ejecutó
en PostgreSQL real; no se infiere concurrencia a partir de un TestCase convencional.

## Errores encontrados y resueltos

- El manager dinámico del usuario no era serializable en migraciones: se convirtió en
  una clase explícita antes de generar/aplicar la migración inicial.
- PowerShell impedía cargar scripts locales: se dejó un lanzador Python de desarrollo,
  sin cambiar políticas del sistema.
- Mensajes de restricciones exponían identificadores técnicos: se agregaron mensajes
  en español con migraciones nuevas, sin reescribir las ya aplicadas.
- Se validó estrictamente el booleano `is_active` del servicio para evitar conversiones
  posteriores que pudieran saltarse las reglas de autodesactivación.
- Hallazgos de formato, importaciones y captura de variable en el script HTTP corregidos;
  Ruff terminó sin errores.

## Comprobaciones pendientes y límites

No hubo navegador conectado: el runtime devolvió «No browser is available» y el listado
de navegadores fue vacío. No se realizaron capturas ni se ejecutó JavaScript en un navegador.
Las pruebas HTTP de HTMX verifican respuestas parciales, autorización y headers, pero
**no** la sustitución visual del DOM ni el comportamiento real de Bootstrap.

Revisión manual pendiente en escritorio (aprox. 1366 px) y móvil (aprox. 390 px):

1. Login correcto/incorrecto, navegación con teclado, labels/foco y cierre de sesión.
2. Listas con filtros, paginación, vacío y overflow horizontal contenido en tablas.
3. Formularios de cuenta/ubicación, errores legibles, creación y edición.
4. Cambio de rol, desactivación/reactivación e historial con datos sintéticos.
5. Filtro HTMX sin recarga completa; botón Atrás; filtros con JavaScript deshabilitado.
6. Sesión expirada, 403 y desconexión de red durante un filtro.
7. Menú Bootstrap móvil, contraste y ausencia de desbordamiento global.

No se ejecutó el workflow en GitHub, despliegue HTTPS real, prueba de restauración de
backups ni limitación de intentos en proxy. `check --deploy` valida configuración, no
demuestra un despliegue seguro. Los módulos posteriores no están implementados ni probados.
