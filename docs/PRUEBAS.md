# Verificación del octavo incremento: incidencias y atención correctiva (fase 12)

**6 de noviembre de 2026, America/Lima.** Prompt completo releído y revisión de modelos,
migraciones, servicios, permisos y dependencias previa a programar. Base: **353 pruebas
OK en 170,006 s**. Regresión completa: **415 pruebas OK en 127,874 s**, PostgreSQL real.
**21 pruebas JavaScript OK**. Ninguna dependencia nueva ni cambio del esquema preventivo.

| Comprobación | Resultado |
| --- | --- |
| `test --noinput` | 415 OK: 353 previas + 62 nuevas, 33 carreras PostgreSQL totales |
| Pruebas focalizadas | 91 OK en 25,187 s; integración/migración/vistas 31 OK en 9,672 s |
| Migraciones | incidents/0001_initial y notifications/0002_incident_notifications aplicadas |
| Conservación en base demo | Hashes de nueve tablas previas idénticos: dispositivo, siete preventivas y notificaciones; nueva FK excluida del hash |
| `sync_roles` | Permisos correctivos y avisos docentes sincronizados |
| `check`, `makemigrations --check --dry-run` | Sin problemas ni cambios pendientes |
| Ruff check/format | Sin errores; 165 archivos Python con formato correcto |
| pip check / collectstatic | Sin incompatibilidades; 0 archivos nuevos, 182 sin cambios |
| `check --deploy --fail-level WARNING` | Correcto con DEBUG=False y origen HTTPS de ejemplo |
| JavaScript | 21 OK, regresión de escáner |
| `smoke_incidents_http.py --confirm-demo --base-url http://127.0.0.1:8007` | Tres cierres, roles, reenvío, CSRF, notas privadas, avisos, ficha y reportes correctos |
| `smoke_dashboard_http.py --confirm-demo --base-url http://127.0.0.1:8007` | Correcto tras ampliar fuentes y bandeja docente |
| `smoke_http.py --qr --maintenance --base-url http://127.0.0.1:8007` | Tres roles y módulos previos correctos |

Pruebas nuevas:

- `test_incidents.py` (24): reporte por tres roles, estado físico sin cambios, UUID/firma,
  validaciones, inactivos/retirados/actor sin permisos, toma y exclusión, versiones,
  propiedad, notas, liberación repetida, relevo técnico, override justificado, tres resultados,
  no reparable con permiso, descarte pendiente, cierre inmutable, reportante inactivo,
  independencia preventiva, constraints/retención y rollback de auditoría/avisos.
- `test_incident_views.py` (20): campos del servidor, errores, docente propio en HTML/HTMX,
  acciones prohibidas, técnico ajeno, PRG/reenvío, no reparable autorizado, privacidad de
  notas/liberaciones, archivo del equipo, ficha integrada, avisos propios y revocación,
  filtros/paginación, restauración HTMX, CSRF/métodos/GET sin escribir, XSS/no-store,
  sesión inactiva, fuente preventiva restringida y ubicaciones de filtro acotadas.
- `test_incident_concurrency.py` (6): conexiones PostgreSQL distintas con barrera y
  lock_timeout; alta duplicada, dos técnicos toman, doble liberación, doble cierre,
  nota contra liberación y liberación contra cierre. Solo una versión se aplica;
  avisos/eventos no se duplican y no se pierde una nota que sí se guardó.
- `test_incident_integration.py` (11): métricas/recurrentes, inválidos excluidos, período,
  filtros, ambas exportaciones, permisos parciales, traslado/archivo, fuente de aviso
  exclusiva, fecha local Lima y paginación de ficha con consultas acotadas.
- `test_incident_migration.py` (1): conserva aviso preventivo de esquema 0001 al agregar
  la nueva fuente; fuente correctiva funciona después y el evento preventivo no cambia.

El test previo de acceso docente a avisos se actualizó: ahora puede consultar su bandeja
correctiva, pero se sigue rechazando acceso revocado/inactivo y fuentes ajenas/preventivas.
Un smoke previo asumía que todo aviso enlazaba a mantenimiento; se corrigió para aceptar
ambas fuentes autorizadas y se repitió satisfactoriamente. Lint/formato corregidos.

HTTP real conservó tres reportes sintéticos: /incidencias/1/ docente, solucionada;
/incidencias/2/ admin, no reparable con justificación; /incidencias/3/ técnico, inválida/
duplicada descartada por admin. Primer caso incluye nota, liberación, toma y aviso al
reportante marcado leído. Un reenvío devuelve el mismo reporte y el segundo cierre se
rechaza. Docente no ve el caso ajeno, notas internas ni reportes del panel. No hay datos reales.

Logs ignorados: `.local/tests-baseline-incidents.txt`, `tests-incident-domain.txt`,
`tests-incidents-focused.txt`, `tests-incidents-integration.txt`, `tests-incidents-full.txt`,
`server-incidents.txt`; los hashes de conservación también son locales. Credenciales y
.env no se versionan. Browser devolvió «No browser is available» y listado vacío: no se
verificó visual/DOM, foco, interacción Bootstrap/HTMX ni diseño impreso en un navegador.
Pendiente revisar en 1366/390 px reporte, filtros, confirmación, notas, cierre, ficha y
contador docente. Continúan pendientes cámara/impresión física, HTTPS/CI remoto y backups.
No se implementó reapertura/rectificación de cierres ni una tarea de avisos del sistema.

## Registro del séptimo incremento: notificaciones y dashboard (fases 9–10)

**6 de noviembre de 2026, America/Lima.** Prompt de 1 145 líneas releído completo;
inspección previa de modelos, migraciones, servicios, permisos y dependencias.
Base: **305 pruebas OK en 161,033 s**. Regresión: **353 pruebas OK en 181,617 s**,
PostgreSQL 18 real; **21 pruebas JavaScript OK**. Tras ajustar el formato horario de
exportación a Lima, **22 pruebas de dashboard OK en 5,876 s**. Sin dependencias nuevas.

| Comprobación | Resultado |
| --- | --- |
| Suite Django | 353 OK; 48 nuevas, cuatro carreras nuevas y 27 concurrentes totales |
| Migración | notifications/0001_initial aplicada; hashes del volcado preventivo iguales antes/después |
| Roles | sync_roles correcto; solo admin/técnico autorizados, docente 403 |
| generate_notifications dos veces | 10 avisos nuevos y después 0; datos demo preservados |
| check / makemigrations --check --dry-run | Sin errores ni cambios pendientes |
| Ruff check / format | Correctos |
| pip check | Sin incompatibilidades |
| collectstatic | 1 archivo nuevo, 181 sin cambios |
| check --deploy --fail-level WARNING | Correcto con DEBUG=False y origen HTTPS de ejemplo |
| JavaScript | 21 OK, sin cambios en escáner |
| smoke_dashboard_http.py --confirm-demo --base-url http://127.0.0.1:8006 | Tres roles; bandeja/contador, cinco tablas/reportes, filtros, lectura propia y rechazo de ajena/CSRF |
| smoke_http.py --qr --maintenance --base-url http://127.0.0.1:8006 | Tres roles y regresión de módulos anteriores correcta |

Pruebas nuevas:

- `test_notifications.py` (21): destinatarios activos/autorizados, deduplicación de
  grupos/eventos, lectura preservada, cada liberación avisa de nuevo, resolución por toma
  y cancelación, siguiente ciclo, fases 7 días/hoy/vencido sin duplicar por día, únicos,
  cambios de intervalo/fecha real/inactivación, comando y backfill de ciclos disponibles,
  rollback al fallar notificación, constraints/retención, bandeja propia, GET sin mutación,
  permisos, lectura POST, CSRF, lectura masiva acotada y paginación.
- `test_dashboard.py` (22): conteos físicos y grupales, equipos sin periódico,
  activos/retirados, fechas reales independientes, omisión pendiente hasta completar otro
  ciclo, únicos, ventana temporal, filtros, cierre por fecha local y límite UTC/Lima,
  estados, validación antes de exportar, cinco tablas e impresión, CSV BOM/filtros,
  HTMX parcial, fórmulas y XSS, límite de exportación, datos legados inválidos visibles,
  docente/anonimato, GET sin escrituras y consulta sin N+1 con 22 equipos.
- `test_notification_concurrency.py` (4): dos conexiones distintas con barrera y
  lock_timeout; dos comandos, comando contra toma, comando contra liberación y doble
  lectura. No duplica avisos ni deja disponibilidad vigente después de tomar.
- `test_notification_migration.py` (1): aplica 0001 sobre datos previos; ejecuciones,
  participantes, tareas, fechas y eventos idénticos; materialización posterior idempotente.

Se corrigió un fixture de fecha UTC que intentaba poner el cierre antes del inicio;
la prueba ahora congela el reloj del flujo completo y respeta la restricción existente.
Los reportes muestran fechas con hora local y offset -05:00. El estado de ejecución
no restringe inventario; los filtros de período mantienen visible el trabajo abierto.

Logs ignorados: `.local/tests-baseline-dashboard.txt`, `tests-notifications-dashboard.txt`,
`tests-full-notifications-dashboard.txt`, `tests-dashboard-final.txt`. Los dumps locales
de conservación no se incluyen en Git, al igual que .env y credenciales demo.

Browser volvió a devolver «No browser is available»; diagnóstico y listado vacío.
No hubo validación visual/DOM en escritorio o móvil. Pendiente comprobar sustitución
HTMX, polling efectivo cada 30 s, navegación con teclado y diseño impreso en navegador.
No se instaló tarea horaria del sistema: procedimiento y comportamiento sin ejecutarla
en MANUAL.md. No se implementaron incidencias ni el aviso opcional de trabajo iniciado.
Siguen pendientes despliegue HTTPS, CI remoto, restauración y pruebas físicas previas.

## Registro del sexto incremento: recurrencia, vencimientos e historial (fase 8)

**6 de noviembre de 2026, America/Lima.** Prompt completo releído y revisión de modelos,
migraciones, servicios, permisos, dependencias y pruebas antes de modificar. Base previa:
**257 pruebas OK en 105,107 s**. Suite final: **305 pruebas OK en 97,483 s**, PostgreSQL
18 real; además **21 pruebas JavaScript OK**. Sin SQLite, paquetes ni tablas nuevos.

| Comprobación | Resultado |
| --- | --- |
| `test --noinput` | 305 OK: 257 previas + 48 nuevas; 23 casos concurrentes totales |
| `migrate`, `sync_roles` | maintenance/0003_recurring_runs aplicada y permisos sincronizados |
| `check`, `makemigrations --check --dry-run` | Sin problemas ni cambios pendientes |
| Ruff check/format | Sin errores; 125 archivos Python con formato correcto |
| `pip check` | Sin incompatibilidades |
| `collectstatic --noinput` | 1 copiado, 180 sin cambios |
| `check --deploy --fail-level WARNING` | Sin problemas con DEBUG=False y origen HTTPS de ejemplo |
| `node --test tests/js/*.test.cjs` | 21 OK |
| `smoke_http.py --qr --maintenance --base-url http://127.0.0.1:8005` | Correcto con tres roles y módulos anteriores |
| `smoke_execution_http.py --confirm-demo --recurrence --base-url http://127.0.0.1:8005` | Flujo operativo + segundo ciclo pendiente + fechas/historial correctos |

Pruebas nuevas:

- `test_recurrence.py`: 26 casos. Fecha base y calendario vigente, caso maestro con
  25/28-11 → 25/28-01 y omitido vencido, límites hoy/7/8 días, creación limpia, subset
  por categoría, cobertura tras cambiar categoría, omisión/cancelación reiteradas,
  último completado por fecha real, cálculo antes de cerrar el grupo, permisos/actor activo,
  reenvíos, versión/predecesor, inactivos/retirados/fuera de servicio, selección temprana,
  configuración futura, reactivación, rollback, constraints y overflow. Selector sin N+1:
  una consulta para todos los equipos y sus ubicaciones/categorías/fechas.
- `test_recurrence_views.py`: 16 casos. Roles/URL/POST, propuesta inicial, errores,
  redirección al ciclo correcto, historial preservado y parent scope, filtro del estado
  más reciente, paginación de 22 ejecuciones y 21 equipos, eventos de un solo ciclo,
  únicos, datos legados inválidos, HTMX/restauración, XSS, no-store, CSRF y métodos.
- `test_recurrence_concurrency.py`: 5 casos con conexiones PostgreSQL independientes,
  barrera y lock_timeout: dos aperturas iguales, selecciones disjuntas, apertura contra
  configuración, desactivación del equipo y cierre anterior. Nunca quedan dos abiertas.
- `test_recurrence_migration.py`: datos con esquema 0002 migrados a 0003, filas/tareas/
  configuración originales intactas; segunda ejecución posible e índice impide otra abierta.
  El test previo de migración restaura ahora las hojas actuales del grafo, conservando
  compatibilidad de la suite al agregar nuevas migraciones.

HTTP real en 8005: creó un periódico sintético `/mantenimientos/4/`, completó un equipo,
omitió otro, cerró parcialmente y abrió la ejecución 2. Confirma tareas nuevas sin marcar,
ausencia de notas del ciclo anterior en el nuevo, notas antiguas conservadas al volver,
reenvío rechazado, exactamente dos filas de historial y eventos filtrados por ciclo.
La segunda ejecución queda pendiente como evidencia. No se modificaron datos reales.

Incidentes corregidos: las pruebas de métodos inseguros debían enviar CSRF válido para
llegar al rechazo 405, pues sin token se rechaza antes con 403. La corrección pasó aislada
y en la repetición completa de 305 casos. Datos legados con intervalo desbordado muestran
un error en calendario/formulario en lugar de 500. Lint/formato corregidos.
Logs locales ignorados: `.local/tests-baseline-recurrence.txt`, `tests-recurrence-domain.txt`,
`tests-recurrence-focused.txt`, `tests-recurrence-final.txt`.

Browser devolvió «No browser is available» y lista vacía. Pendiente revisión visual en
escritorio/móvil de calendario, filtros HTMX, selección propuesta, motivo anticipado,
historial paginado y retorno entre ciclos. HTTP no certifica DOM/foco/teclado ni Bootstrap.
HTTPS real, CI remoto, restauración de backups y pruebas físicas QR siguen pendientes.
No se implementaron notificaciones, dashboard ni incidencias. Siguiente fase: notificaciones.

## Registro del quinto incremento: ejecución preventiva (fase 7)

**6 de noviembre de 2026, America/Lima.** Prompt completo releído e inspección de modelos,
migraciones, servicios, permisos y dependencias antes de modificar. Base previa: **197
pruebas OK en 62,304 s**. Regresión completa: **257 pruebas OK en 126,210 s**, PostgreSQL
real; además **21 pruebas JavaScript OK**. Sin SQLite ni dependencias nuevas.

| Comprobación | Resultado |
| --- | --- |
| `test --noinput` | 257 OK: 197 previas + 60 nuevas; dieciocho casos concurrentes totales |
| `test tests.test_execution_concurrency tests.test_execution_migration --noinput` | 8 OK en 31,742 s |
| `migrate`, `sync_roles` | maintenance/0002_execution_workflow aplicada y permisos sincronizados |
| `check`, `makemigrations --check --dry-run` | Sin problemas ni cambios pendientes |
| Ruff check/format | Sin errores; 116 archivos Python con formato correcto |
| `pip check` | Sin incompatibilidades |
| `collectstatic --noinput` | 0 copiados, 181 sin cambios |
| `check --deploy --fail-level WARNING` | Sin problemas con DEBUG=False y origen HTTPS de ejemplo |
| `node --test tests/js/*.test.cjs` | 21 OK |
| `smoke_http.py --qr --maintenance --base-url http://127.0.0.1:8004` | Correcto para tres roles |
| `smoke_execution_http.py --confirm-demo --base-url http://127.0.0.1:8004` | Flujo operativo correcto; cierre parcial sintético conservado en /mantenimientos/3/ |

Nuevas pruebas:

- `test_execution.py`: 34 casos. Toma sin inicio, inicio único, liberación/reanudación
  conservando datos, responsable activo, intervención administrativa, tareas/notas,
  rectificación con motivo, independencia entre equipos, opcionales, verificación/resumen,
  fechas autorizadas, vencimientos por equipo, omisión, cierre total/parcial, todos
  omitidos, cancelación, rechazo tras cierre, rollback, versiones y restricciones DB.
  El caso maestro se reforzó al final y volvió a pasar: base 01/10/2026, vencimiento
  01/12, completados 25 y 28/11 → 25 y 28/01/2027; omitido conserva 01/12.
- `test_execution_views.py`: 18 casos. Permisos/URL, GET sin escritura, POST/PRG,
  actor/estado/fecha inyectados, flujo completo, versiones, errores y entradas conservadas,
  IDOR de tareas/equipos, reanudación, filtros HTMX, eventos en español, XSS, privacidad,
  CSRF, métodos y reenvío sin duplicar historia.
- `test_execution_concurrency.py`: 7 casos con conexiones PostgreSQL distintas, barrera
  y lock_timeout: dos tomas, dos inicios, liberar/avanzar, completar/omitir, cerrar/rectificar
  tarea general, cambiar intervalo/completar y trasladar/avanzar.
- `test_execution_migration.py`: datos creados con esquema 0001 migrados a 0002 en BD
  temporal; configuración, equipo, tarea y fecha conservados, valores operativos iniciales
  correctos y toma posterior válida. Restaura esquema al terminar.

El smoke operativo crea por formulario/CSRF un preventivo sintético de dos equipos y
verifica toma/inicio/avance, liberación, retoma/reanudación, completado, omisión, avance
general, cierre parcial e historial; conserva notas anteriores a liberar y rechaza toma
administrativa/docente. Requiere servidor local y --confirm-demo. El registro se conserva.

Incidentes corregidos: fixture run ocultaba unittest.TestCase.run; la anotación de progreso
retiraba el orden implícito (ahora due_date/PK explícitos). Lint/formato corregidos. El
PostgreSQL local dejó de responder durante la continuación: se reinició sin borrar datos;
las verificaciones finales se ejecutaron después. Logs en `.local/tests-execution-*.txt`.

No hubo navegador conectado: Browser devolvió «No browser is available» y lista vacía.
Pendiente revisión visual escritorio/móvil de formularios, errores, checklists, notas,
detalle grupal, foco/teclado y estados tras liberar/reanudar. HTTP no demuestra DOM ni
interacción Bootstrap. HTTPS real, CI remoto, backups y hardware QR siguen pendientes.

Límites: no se revierte equipo completado/omitido ni cierre; no se abren ciclos siguientes
ni se emiten notificaciones. RELEASED conserva cada liberación para futura integración.

## Registro del cuarto incremento: configuración preventiva (fase 6)

**6 de noviembre de 2026, America/Lima.** Prompt completo releído y estado/modelos/
migraciones/servicios/permisos revisados. PostgreSQL local estaba detenido: primer intento
agotó conexión; se reinició el clúster aislado conservando datos. Base previa: **145 pruebas
OK en 41,309 s**. Suite final: **197 pruebas OK en 63,763 s**, con PostgreSQL 18.4 real.
Además **21 pruebas JavaScript OK** de regresión QR. Ninguna prueba usa SQLite.

| Comprobación | Resultado |
| --- | --- |
| `test --noinput` | 197 OK: 145 previas + 52 nuevas; once casos concurrentes en total |
| `node --test tests/js/*.test.cjs` | 21 OK |
| `migrate`, `sync_roles` | maintenance/0001_initial aplicada, permisos de tres roles sincronizados |
| `check`, `makemigrations --check --dry-run` | Sin problemas ni cambios pendientes |
| Ruff check/format | Sin errores; 106 archivos Python con formato correcto |
| `pip check` | Sin incompatibilidades; no se añadieron dependencias |
| `collectstatic --noinput` | 2 copiados, 179 sin cambios |
| `check --deploy --fail-level WARNING` | Sin problemas con DEBUG=False y origen HTTPS de ejemplo |
| `smoke_http.py --qr --maintenance --base-url http://127.0.0.1:8003` | Correcto con los tres roles |
| `seed_maintenance_demo --confirm-demo` | Único y periódico creados pendientes, sin registrar trabajo realizado |

Pruebas nuevas:

- `test_maintenance.py`: 31 casos (calendario/dominio/demo). Días, meses, bisiestos,
  overflow, fechas incoherentes, creación individual/grupal heterogénea, categorías,
  tareas opcionales/generales, equipos inactivos/retirados, reintentos, versiones, motivo,
  no-op, copias independientes, retención, DB constraints, rollback y traslado sin efecto
  preventivo. Demo explícita e idempotente. Los ejemplos de fechas futuras prueban solo
  la función de calendario; no equivalen a ejecutar/completar equipos ni generar otro ciclo.
- `test_maintenance_views.py`: 18 casos. Roles/URL directa, creación/reenvío, tipo y fechas
  por defecto en Lima, errores, formset/orden/omisión/categoría, fila adicional sin JS ni
  guardado, límites, edición por versión, filtros HTMX/restauración, paginación, XSS, CSRF,
  ausencia de rutas operativas, admin readonly y confirmación de traslado pendiente.
- `test_maintenance_concurrency.py`: 3 casos con conexiones PostgreSQL distintas,
  barrera y timeout. Mismo envío simultáneo crea una ejecución; misma clave con equipos
  diferentes rechaza uno; dos ediciones no sobrescriben tareas ni historial.

Defectos detectados y corregidos: helper de prueba de overflow repetía un argumento;
alta de fila adicional necesitaba sus valores iniciales para no convertir una fila vacía
en una tarea modificada inválida; se añadió comprobación explícita. Lint/formato corregidos.
Todos los casos pasan después de los cambios. Logs: `.local/tests-baseline-maintenance.txt`,
`.local/tests-maintenance-focused.txt`, `.local/tests-maintenance-final.txt` (ignorados).

HTTP real verifica autenticación, permisos, listado, detalle pendiente, historial, formularios
único/periódico y filtros parciales, además de las rutas previas de activos/QR. No acredita
render visual ni funcionamiento DOM. Browser devolvió «No browser is available» y lista vacía.

Pendiente manual: revisar formulario en escritorio/móvil; selección de equipos, tareas por
categoría, orden, eliminar y agregar filas sin perder datos; errores legibles; navegación;
filtrado HTMX real; mostrar copias conservadas tras edición y confirmación de traslado.
No se probaron toma/inicio/liberación/avance/cierre/ciclos posteriores: están fuera de fase 6.
HTTPS/proxy real, CI remoto, restauración de backups y verificaciones físicas QR siguen pendientes.

## Registro del tercer incremento: QR, etiquetas y escáner

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
