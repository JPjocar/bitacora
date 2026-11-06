# Verificación del tercer incremento: QR, etiquetas y escáner

**6 de noviembre de 2026, America/Lima.** Se releyeron las 1.145 líneas del prompt y
se revisaron modelos, migraciones, servicios, permisos y dependencias existentes.
Base anterior: **116 pruebas OK en 51,334 s**. Suite final: **145 pruebas Django OK
en 58,155 s**, sobre PostgreSQL 18.4 real, sin SQLite. JavaScript: **21 pruebas OK**
con Node y dispositivos simulados. No hay navegador/cámara física conectados.

| Comprobación | Resultado |
| --- | --- |
| `test --noinput` | 145 OK, incluidas las ocho pruebas concurrentes previas |
| `node --test tests/js/*.test.cjs` | 21 OK; cancelación, cierre, errores y adaptación del formulario |
| `migrate`, `sync_roles` | `assets/0004_alter_device_options` aplicada; tres roles sincronizados |
| `check`, `makemigrations --check --dry-run` | Sin problemas ni migraciones pendientes |
| `pip check`, Ruff lint/formato | Sin incompatibilidades ni errores |
| `collectstatic --noinput` | 6 copiados, 174 sin cambios |
| `check --deploy --fail-level WARNING` | Sin problemas con DEBUG=False y origen HTTPS de ejemplo |
| `smoke_http.py --qr --base-url http://127.0.0.1:8002` | Correcto para admin/técnico/docente; incluye checks anteriores |

`tests/test_qr.py`: 29 casos. El decodificador independiente zxing-cpp confirma el
contenido exacto de PNG, margen blanco y legibilidad digital aproximada a 32 mm/300 dpi.
Se verifican persistencia del QR tras edición/traslado, Host distinto, login con retorno,
roles/visibilidad, CSRF, URL maliciosa/externa/malformada, código manual, equipos no visibles,
impresión individual, duplicados, límite de selección, hojas de 15 y ausencia de mutaciones.
Los checks rechazan orígenes inválidos y HTTP en la comprobación de despliegue.

`tests/js/qr-controller.test.cjs` (13 casos) prueba serialización con promesas diferidas:
cierre antes/durante/después del arranque, resultados repetidos/tardíos, sustitución de
imagen, cierre antes de leer archivo, errores de permisos/dispositivos/parada y reintento.
`tests/js/scanner.test.cjs` (8 casos) usa un DOM simulado para los eventos del modal/página,
mensajes, HTTP inseguro, biblioteca ausente, archivos inválidos, envío seguro y liberación
de pistas. No se ejecutó html5-qrcode con una cámara real ni en un navegador.

El smoke HTTP autentica las tres cuentas demo, obtiene y decodifica PNG reales, envía
código y URL por POST con CSRF, rechaza URL externa, comprueba permiso de etiquetas y
deduplicación, y descarga los estáticos nuevos. No produce datos de negocio. Salida de
suite en `.local/tests-qr.txt`; secretos y logs locales permanecen ignorados por Git.

Limitaciones verificadas: Browser devolvió «No browser is available» y una lista vacía.
Pendientes: escritorio/móvil visual, sustitución HTMX en DOM real, Bootstrap modal real,
cámara frontal/trasera y sus permisos, lectura desde archivo en navegador, cámara móvil
normal → login → ficha, y una hoja física A4 con lectura posterior. La prueba digital
del PNG no certifica impresión, márgenes del driver ni funcionamiento en teléfonos.
HTTPS/proxy, ejecución CI remota y restauración de backups siguen pendientes.

Lista manual para completar cuando haya dispositivo e impresora:

1. Configurar origen público HTTPS alcanzable; probar el enlace desde otra máquina.
2. Imprimir 1, 15 y 16 etiquetas a 100 % en A4, sin encabezados/pies; verificar código
   completo, QR/margen blanco, nombre breve y cambio de hoja sin duplicados/recortes.
3. Leer etiquetas con cámara nativa sin sesión y confirmar retorno a ficha por cada rol.
4. En escáner integrado permitir/denegar cámara, ocuparla desde otra app, cerrar modal
   durante solicitud y después del inicio, ocultar pestaña y confirmar indicador apagado.
5. Probar PNG/JPG/WebP válidos, imagen sin QR, archivo incorrecto, QR externo/no existente
   y búsqueda manual. Repetir en móvil/escritorio, con HTTP local y HTTPS.
6. Filtrar dispositivos por HTMX, seleccionar e imprimir; confirmar pérdida informada
   de selección al cambiar página/filtros y ausencia de impresión para docente.

## Registro del segundo incremento: dispositivos y movimientos

**6 de noviembre de 2026, America/Lima.** Mismas versiones y PostgreSQL 18.4 real.
Antes de modificar código se ejecutaron las 62 pruebas existentes: OK en 35,185 s.
La suite completa final pasó con **116 pruebas, 53,140 s**, incluyendo ocho casos
TransactionTestCase con conexiones PostgreSQL independientes.

| Verificación | Resultado |
| --- | --- |
| Migraciones `assets/0001`, `0002`, `0003` | Aplicadas; ninguna migración anterior eliminada |
| Suite completa `test --noinput -v 2` | 116 OK (62 anteriores + 54 nuevas) |
| `check`, `makemigrations --check --dry-run` | 0 problemas; sin cambios pendientes |
| HTTP real en `127.0.0.1:8001`, `smoke_http.py --assets` | Login, roles, listas, fichas, categorías, formularios, movimientos, fragmentos y assets correctos |
| Ruff lint y formato | Sin errores; 82 archivos Python formateados |
| `pip check` | Sin dependencias incompatibles |
| `collectstatic --noinput` | 3 copiados, 171 sin cambios |
| `check --deploy --fail-level WARNING`, DEBUG=False | 0 problemas |

Salida local: `.local/tests-assets-full.txt`. La demo adicional se creó mediante
`seed_assets_demo --confirm-demo`, usando las cuentas demo existentes y sin cambiar
contraseñas. La verificación HTTP no equivale a ejecutar JavaScript en un navegador.

Pruebas nuevas:

- `test_assets.py`: 19 casos de categorías, datos opcionales por tipo, fechas, permisos,
  identificadores inmutables, colisiones de códigos, límites, integridad, archivo y rollback.
- `test_movements.py`: 13 casos de origen/actor reales, destino activo y diferente, motivo,
  fechas, reenvíos, advertencias, movimientos de inactivos, atomicidad y conservación.
- `test_asset_views.py`: 18 casos de formularios, matriz de roles, privacidad docente por
  URL directa, CSRF, XSS, búsquedas/paginación, errores y respuestas HTMX.
- `test_asset_concurrency.py`: 4 casos con conexiones distintas: traslados incompatibles
  del mismo dispositivo; traslado contra edición; intercambio de ubicaciones de dos
  equipos sin bloqueo circular; desactivación del destino concurrente con traslado.

Defectos/incidentes encontrados y corregidos:

- Una prueba detectó que `TextField.max_length` no validaba por sí solo llamadas directas
  al servicio: se añadieron MaxLengthValidator y una nueva migración, sin alterar las aplicadas.
- Se usó NO KEY UPDATE en destinos para permitir las comprobaciones de FK de traslados
  cruzados; una prueba fuerza ambos destinos bloqueados antes de guardar los movimientos.
- El clúster local se detuvo durante el trabajo; se comprobó su estado y se volvió a
  iniciar conservando los datos. Las pruebas finales se ejecutaron después del reinicio.

Pendiente: revisión visual escritorio/móvil y ejecución JS. El intento de conectar un
navegador devolvió «No browser is available». Revisar manualmente búsqueda HTMX, fichas
por rol, creación con errores y confirmación de traslado en móvil/escritorio. No hay
capturas simuladas. En ese incremento no se probó mantenimiento/incidencias/QR.
Permanece pendiente CI remoto, HTTPS/proxy real y restauración de backups.

## Registro histórico de la primera entrega (usuarios, roles y ubicaciones)

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
