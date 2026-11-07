# Arquitectura

Una aplicación Django, un proceso web desplegable y una base PostgreSQL.
HTML generado por Django Templates; Bootstrap 5.3 y HTMX 2 se sirven localmente.
No hay SPA, API REST, colas, microservicios ni capa Repository.

| Componente | Responsabilidad |
| --- | --- |
| `config` | Entorno, rutas, middleware, WSGI/ASGI y seguridad |
| `apps.accounts` | Usuario extendido, autenticación, roles, servicios y eventos de cuentas |
| `apps.locations` | Ambientes, validación, servicios y eventos de ubicaciones |
| `apps.assets` | Categorías, dispositivos, movimientos, auditoría, QR, etiquetas y resolución del escáner |
| `apps.maintenance` | Configuración, inscripciones, plantillas, primera ejecución y copias históricas |
| `apps.core` | Clases abstractas de conservación/auditoría, permisos y presentación compartida |
| `templates`, `static` | Interfaz en español, componentes Bootstrap y filtros HTMX |
| `tests` | Pruebas funcionales, de seguridad y transacciones concurrentes |

Flujo de escritura: vista autorizada → formulario → servicio → validación dentro de
`transaction.atomic` → modelo + evento. La auditoría se guarda en la misma transacción:
si falla, se revierte el cambio. La autenticación/sesiones siguen las APIs nativas Django.

Las ubicaciones dependen solo de la referencia al usuario y de helpers compartidos.
`accounts` no importa `locations` en su dominio; el comando de demostración integra ambos.
El aprovisionamiento de roles conoce explícitamente los permisos disponibles de esta entrega.
No hay señales para encadenar operaciones críticas.

Los cambios de cuentas bloquean la fila del grupo Administrador y luego la cuenta:
un bloqueo común serializa cambios de roles y protege la existencia de un administrador
activo. Es adecuado para la administración de cuentas de un piloto pequeño. Los cambios
de ubicación bloquean solo la ubicación. Ambos usan `version` para rechazar formularios viejos.

Los modelos concretos se administran desde las pantallas del producto. Django Admin es
de solo lectura y no registra Group para evitar escrituras que salteen los servicios.
El operador con acceso a shell/SQL tiene una frontera de confianza mayor; véase seguridad.

QR usa qrcode/Pillow en servidor y html5-qrcode local en el navegador. Gráficos y otros
módulos siguen pendientes. No hay API REST ni almacenamiento de imágenes subidas.

`assets` agrupa dispositivos y movimientos porque la ubicación actual y su evento de
traslado deben cambiar en una sola transacción. Consume Location mediante FK PROTECT;
no cambia nombres, tipos ni estado de ubicaciones. `selectors.visible_devices` aplica
el alcance docente tanto a la lista como al acceso directo a una ficha.

Una edición/traslado bloquea el dispositivo y comprueba su versión. La selección de
destino usa `select_for_update(no_key=True)`: serializa desactivaciones y permite las
comprobaciones FK de otros traslados, evitando bloqueos circulares al intercambiar dos
equipos entre ambientes. El aviso preventivo usa un selector de lectura de maintenance;
el traslado no escribe en sus modelos. Se comprueba bajo bloqueo del equipo.

`assets.qr` genera PNG en memoria y valida selecciones/lecturas contra los dispositivos
visibles. `qr_views` contiene vistas HTML y el formulario de lectura. La identidad y la
ruta de ficha se reutilizan: sin modelo QR, tabla de lotes, archivos media ni auditoría
de lectura. El navegador envía texto por formulario POST con CSRF; el servidor resuelve
una ficha relativa autorizada. El controlador JS serializa inicio/parada/imagen y
descarta respuestas tardías después de cancelar. Los tests Node no son tests de navegador.

`maintenance.services.save_maintenance` valida toda la configuración y la guarda junto
a equipos, tareas, primera ejecución y auditoría en una transacción. Reutiliza modelos
protegidos y autorización de core, sin señales. Bloquea equipos por PK y después categorías
(NO KEY UPDATE); al editar bloquea primero el mantenimiento y exige versión. Es compatible
con el orden de bloqueo de activos. Las copias de tareas se insertan en lotes transaccionales.

Clave UUID de envío y firma del contenido evitan altas duplicadas; UNIQUE resuelve también
la carrera entre selecciones distintas. La clave no autoriza acceso. Editar configuración
no cambia ejecuciones existentes. El formset Django limita tareas, permite ordenar/quitar
y agregar filas por POST sin guardar, incluso sin JavaScript. HTMX solo actualiza filtros.

`maintenance.execution` concentra las operaciones de trabajo. Orden de bloqueo:
mantenimiento → ejecución → participante/tareas. Primero se comprueban versión y actor
recargado; toda escritura y evento se confirman juntos. El bloqueo del mantenimiento
serializa cambios de intervalo contra cálculo por fecha real. El de ejecución impide
doble toma/cierre y pérdida de avances. Los joins del cierre solo bloquean participantes,
sin bloquear equipos/ubicaciones ajenos a la operación.

`execution_forms` y `execution_views` proporcionan páginas HTML de confirmación/avance
con POST y PRG. Cada formulario lleva versión; no se confían actor, estado ni fechas
automáticas al cliente. La vista compartida de mantenimiento presenta estado/responsable,
progreso y acciones autorizadas, conservando un único concepto de mantenimiento.
No se añadió API, notificador ni reloj de trabajo.

`maintenance.recurrence.create_next_run` bloquea mantenimiento → predecesor → equipos
por PK → categorías, compatible con ejecución y configuración. Exige cierre previo,
versión y predecesor vigentes. Comparte create_run_snapshot con el alta inicial: evita
duplicar generación de participantes/tareas. La auditoría se confirma con las copias.
El índice parcial de una ejecución abierta refuerza en PostgreSQL el flujo del MVP.

`selectors.target_schedule` deriva fechas sin escrituras ni consultas por cada equipo:
Subquery para la fecha real más reciente y su ejecución fuente, luego add_interval probado
para días/meses. SOON_DAYS=7 delimita propuestas. Omitidos/cancelados no son anclas.
Configurar un intervalo valida también el cálculo frente a completados existentes para
evitar desbordamientos. Un dato legado inválido se presenta con error, sin generar ciclos.

Historial paginado y URL por ejecución con parent scope. El listado principal usa
Subquery para estado/responsable del último ciclo, sin cargar todas las ejecuciones.
Las fechas vigentes y las copias históricas se muestran separadamente. Solo GET para
consultas y POST/CSRF para apertura; no cron ni trabajo generado por alcanzar una fecha.
