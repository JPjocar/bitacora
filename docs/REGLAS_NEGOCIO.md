# Reglas implementadas

| Operación | Administrador | Técnico | Docente |
| --- | --- | --- | --- |
| Ingresar, salir, consultar su perfil, cambiar su contraseña | Sí | Sí | Sí |
| Consultar/crear/editar/desactivar/reactivar usuarios | Sí | No | No |
| Asignar uno de los tres roles y consultar permisos | Sí | No | No |
| Restablecer contraseña de otra cuenta de negocio | Sí | No | No |
| Consultar ubicaciones | Sí | Sí | No |
| Crear/editar/desactivar/reactivar ubicaciones | Sí | No | No |
| Consultar auditoría de cuentas y ubicaciones | Sí | No | No |
| Consultar categorías | Sí | Sí | No |
| Crear/editar/desactivar categorías y dispositivos | Sí | No | No |
| Consultar ficha técnica, serie, notas e historial de dispositivos | Sí | Sí | No |
| Consultar ficha limitada de equipos activos no retirados | Sí | Sí | Sí |
| Actualizar estado y observaciones del dispositivo | Sí | Sí | No |
| Registrar/consultar movimientos | Sí | Sí | No |
| Escanear cámara/imagen/código y ver QR de equipos visibles | Sí | Sí | Sí, ficha limitada |
| Imprimir etiquetas individuales o por selección | Sí | Sí | No |
| Configurar/editar/desactivar mantenimientos preventivos | Sí | No | No |
| Consultar mantenimientos, primera ejecución y auditoría | Sí | Sí | No |
| Tomar como responsable | No | Sí | No |
| Iniciar/reanudar, avanzar, liberar, omitir, completar y cerrar | Con motivo administrativo | Solo su ejecución | No |
| Registrar fecha real anterior | Con motivo | No, salvo permiso explícito | No |
| Crear siguiente ejecución y consultar vencimientos/historial | Sí | Sí | No |
| Eliminar físicamente registros o modificar eventos | No | No | No |

Las comprobaciones se basan en permisos Django, no solo en nombres de grupos o botones.
Anónimos: redirección a login; autenticados sin permiso: 403, también en HTMX.
Cada cuenta solo consulta su perfil en `/cuentas/perfil/`, sin un ID modificable.

Un administrador no puede desactivarse ni cambiar su propio rol. No se puede retirar
el último administrador de negocio activo, ni siquiera con dos peticiones concurrentes.
El superusuario técnico se crea explícitamente por consola y no puede ser modificado
desde la gestión de usuarios. No se permite elevar `is_staff`/`is_superuser` desde formularios
o datos extra enviados a los servicios.

Contraseña inicial obligatoria, confirmada y validada (mínimo 12 caracteres, sin valores
comunes, solo numéricos o similares a los datos personales). Hashing nativo Django.
El cambio personal exige la contraseña actual y conserva la sesión actual. Restablecer
la contraseña invalida sesiones anteriores. Desactivar impide autenticación y acceso
en solicitudes posteriores. Reactivar es una edición autorizada y auditada.

Los roles son una política fija: no hay editor arbitrario de permisos. `sync_roles`
sincroniza la matriz de esta entrega y es idempotente. Su ejecución debe formar parte
del despliegue y coordinarse con cambios de permisos de futuros módulos.

Ubicación: nombre y tipo obligatorios, código opcional. Se impiden nombres/códigos
duplicados ignorando mayúsculas y espacios periféricos. Desactivar conserva todos los
eventos; reactivar no crea una entidad nueva. Desactivar una ubicación no mueve ni borra
sus equipos. Se impiden nuevas altas/traslados hacia ella, pero se permite trasladar
equipos fuera de ella. Las referencias existentes usan PROTECT.

Los formularios llevan versión del registro. Guardar una versión antigua muestra un
error y obliga a recargar; no sobrescribe cambios ajenos. Un guardado sin cambios no
crea eventos adicionales. Un reenvío de edición ya aplicada se rechaza por versión.
Las altas duplicadas se rechazan por unicidad; no se crean dos registros iguales.

GET/HEAD no modifican datos de negocio. Escrituras por POST con CSRF y patrón
POST–Redirect–GET. HTMX se usa solo en filtros GET; sin JavaScript funcionan filtros
y formularios mediante navegación convencional. Sesión expirada en HTMX redirige la
página completa; errores de red/403 tienen mensajes en el frontend.

Dispositivos:

- Código `EQ-` + 8 caracteres aleatorios con `secrets.choice`; alfabeto sin O/0/I/1/L.
  Unicidad PostgreSQL, hasta ocho intentos ante colisión, código y UUID inmutables en
  servicios, formularios y operaciones ORM públicas protegidas. No constituyen autorización.
- Nombre, categoría y ubicación inicial obligatorios. Marca/modelo, serie, detalles
  técnicos, observaciones y fechas opcionales. La serie no es universalmente única.
- Categorías iniciales PC, Laptop, Router, Impresora, Monitor y Otros. Categorías
  inactivas se conservan en equipos existentes, pero no se asignan a nuevos equipos.
- Fechas de hechos realizados: no futuras; puesta en servicio no anterior a adquisición
  cuando ambas existen. Los textos largos tienen límites también en los servicios.
- Técnico solo actualiza estado/observaciones. Cambiar estado exige motivo; no se
  permite cambiar ficha, ubicación, categoría, identidad ni activo desde esa operación.
- Activo en el registro y estado operativo son conceptos separados. Archivar no altera
  resultados físicos, identidad ni historial. No existe estado «En mantenimiento».
- Docente ve nombre, código, categoría, marca/modelo, ubicación y estado, solo de equipos
  activos no retirados. No ve serie, notas, detalles técnicos, fechas administrativas,
  actores ni movimientos. Cambiar el UUID en URL no permite acceder a un equipo excluido.

Movimientos:

- Representan traslados ya realizados, sin estados de solicitud/aprobación/tránsito.
- Origen y actor se obtienen en servidor; destino existente, activo y diferente del origen.
  No se habilita una excepción de origen=destino porque no fue solicitada.
- Motivo obligatorio; observaciones opcionales; fecha efectiva aware en Lima, no futura
  ni anterior al último traslado del equipo. Se admite registro extemporáneo en orden.
- Fuera de servicio, retirado o inactivo: advertencia con confirmación expresa en servidor,
  seguida del traslado permitido. El estado operativo y activo permanecen iguales.
- Guardar movimiento, actualizar ubicación/versión y auditar es atómico. Un error revierte
  todo. Dos formularios con la misma versión no producen dos traslados incompatibles.
- No se editan ni eliminan movimientos anteriores. Una ubicación o equipo referenciado
  no se elimina. La consulta histórica muestra la identidad de ubicación y su nombre actual.
- Un traslado no registra reparación ni preventivo. Si existe una ejecución preventiva
  pendiente, exige confirmar la advertencia y conserva tareas, participación y fechas.

QR y etiquetas:

- Solo codifican el origen público configurado y la ruta de ficha con UUID. No incluyen
  código interno, datos técnicos, ubicación, contraseñas ni permisos. Editar o trasladar
  el equipo no modifica la identidad ni el PNG mientras se conserve el mismo origen.
- La ficha, el PNG y el escáner exigen sesión y alcance por objeto. Login conserva la
  ficha de destino. Un UUID/código conocido nunca habilita una ficha excluida.
- El escáner acepta el código alfanumérico normalizado o una URL de ficha del origen
  configurado, sin credenciales, parámetros ni fragmentos. No abre URLs externas ni
  rutas administrativas. Equipo desconocido/no visible produce el mismo mensaje.
- Impresión para administrador/técnico: 1–100 identificadores por solicitud, duplicados
  eliminados, selección inválida rechazada completa, hasta 15 etiquetas por hoja A4.
  Interfaz: selección sobre la página actual, reiniciada al filtrar/paginar.
- Imprimir/escanear no crea lotes de negocio, movimientos, eventos ni cambios de estado.
  La imagen del escáner se procesa localmente y no se sube al servidor.

Configuración preventiva (fase 6):

- Un concepto Mantenimiento admite 1–200 equipos y 1–50 tareas. No hay Jornadas.
- Único: fecha prevista. Periódico: fecha base e intervalo entero positivo en días/meses
  calendario. Valores iniciales en Lima. Fechas pasadas/futuras nunca acreditan trabajo.
- Primer vencimiento por equipo = base + intervalo. En meses se limita el día al último
  del mes de destino. El único usa la fecha prevista. Se guarda una copia por participante.
  Al completar se conserva además el siguiente vencimiento calculado desde su fecha real.
- Nuevas inscripciones: equipos activos no retirados; fuera de servicio está permitido.
  Inscritos que después se inactivan se conservan. Quitar una inscripción futura no borra
  al participante existente. Reactivar reutiliza la inscripción.
- Cada equipo necesita al menos una tarea individual aplicable; puede ser opcional.
  La categoría debe estar representada entre los equipos elegidos. Tareas generales sin
  categoría: una copia por ejecución. Nombres normalizados no duplicados por ámbito/categoría.
- Creación atómica: configuración, primera ejecución pendiente sin asignar/iniciar,
  participantes Sin finalizar, tareas sin completar y auditoría.
- Edición con versión vigente y motivo: cambia configuración, no las copias existentes,
  incluso si están pendientes. Base/intervalo nuevos solo afectan ciclos futuros.
  No cambia tipo único/periódico ni reprograma fecha del único. Desactivar no cancela.
- Reenvío con misma clave/contenido no duplica. Clave usada con contenido distinto se
  rechaza. Ediciones simultáneas no sobrescriben cambios ni duplican historial.
- Docente sin acceso por URL/HTMX; Django Admin solo lectura.

Ejecución preventiva (fase 7):

- PENDIENTE_ATENCION sin responsable; Tomar por técnico pasa a ASIGNADO sin inicio.
  Iniciar pasa a EN_EJECUCION y fija started_at una vez. Liberar desde asignado/en ejecución
  exige trabajo realizado/motivo, vuelve a pendiente y quita solo asignación. Retomar exige
  Iniciar/Reanudar; registra RESUMED y conserva el primer inicio.
- Avance, notas, omisión y completado solo en EN_EJECUCION. Técnico responsable o permiso
  administrativo con motivo; autor y fechas se generan en servidor. Cualquier cambio
  aumenta versión global de ejecución, evitando sobrescribir formularios antiguos.
- Check/observación guardan último actor/fecha y un evento antes/después. Notas opcionales
  generales/por equipo, sin exigir una por cada tarea. Desmarcar una tarea realizada exige
  motivo; equipo ya completado/omitido no permite rectificación ni cambio de resultado.
- Completar equipo exige tareas individuales obligatorias, verificación final y resumen
  de hasta 300 caracteres. La fecha del técnico es hoy en Lima; fecha anterior exige permiso
  específico y motivo, sin fechas futuras. Se admite registro extemporáneo autorizado aun
  si la fecha efectiva antecede al registro/inicio en la aplicación. La fecha registrada
  automáticamente permanece actual y auditable.
- Próximo vencimiento calculado = fecha real del equipo + intervalo vigente al completar.
  Se almacena en el participante, conservando su due_date original. Es una copia histórica
  del cálculo, no la apertura de un siguiente ciclo. Único no obtiene próxima fecha.
- Omitir conserva tareas/notas, motivo, actor, fecha y fila; no registra fecha real ni
  próxima fecha y no altera due_date. Puede trasladarse antes/después sin cambiar resultado.
- Cerrar solo en ejecución: todos completados => COMPLETADO; al menos un completado y
  resto omitidos => COMPLETADO_PARCIALMENTE. En ambos, tareas generales obligatorias
  cumplidas, sin SIN_FINALIZAR. Todos omitidos no admite parcial: permite cancelar.
- Cancelar exige motivo y ciclo abierto; técnico solo el suyo, administrador también
  pendientes sin responsable. Prohibido si hay equipos completados. Conserva checks y
  notas de trabajo incompleto. No genera preventivos válidos ni altera fechas.
- Cierre general guarda timestamp/actor independientes de la fecha civil de cada equipo.
  No se permite revertir completados o cierres; una corrección requiere diseñar un flujo
  administrativo posterior. Sin reprogramación, cronómetro ni inicio por computadora.
- Avisos de traslado incluyen pendiente/asignado/en ejecución con equipo sin finalizar.
  Configuración inactiva no cancela ni bloquea terminar el trabajo ya creado.

Recurrencia e historial (fase 8):

- Fecha vigente por inscripción activa = fecha real más reciente de un participante
  COMPLETADO + intervalo vigente. Sin completados: base vigente + intervalo. El orden
  se basa en la fecha efectiva, no en fecha de registro/número de ciclo: un registro tardío
  de trabajo antiguo no hace retroceder el calendario. Un equipo completo ya es válido
  aunque el resto del grupo siga abierto. Omitidos/cancelados/pendientes no aportan ancla.
- due_date de la participación y next_due_date calculado al completarla son historia.
  Cambiar base/intervalo recalcula consultas y próximos ciclos, no esas copias. Sin último
  completado, cambiar la base afecta la fecha inicial futura; con completado se usa su fecha.
- «Próximo» significa dentro de 7 días civiles de Lima; vencido, hoy y posterior se derivan
  al consultar, sin estados persistidos ni ejecución automática.
- Una sola ejecución abierta por mantenimiento, respaldada por índice único parcial.
  Crear siguiente exige periódico activo, cierre/cancelación previa, versión de configuración
  y predecesor vigentes, permiso específico y 1–200 inscripciones activas de ese mantenimiento.
  Técnicos y administradores tienen el permiso; docente no.
- Se proponen vencidos/hoy/próximos disponibles. Se permite incluir otros activos no retirados
  con motivo obligatorio. Fuera de servicio no impide selección. Inactivos/retirados conservan
  fecha e historia, pero no entran al nuevo ciclo. Quitar/reactivar inscripción conserva identidad.
- Nueva ejecución numerada correlativamente, pendiente, sin responsable/inicio/notas.
  Copia tareas actuales según categoría/ámbito, sin marcas/observaciones/actores anteriores.
  Cada equipo debe conservar cobertura individual. Un cambio de categoría puede requerir
  corregir las plantillas antes de crear otro ciclo. Las generales se copian una sola vez.
- Reenvío con predecesor antiguo o versión obsoleta se rechaza, incluso si el ciclo nuevo
  ya cerró. Creación/copias/evento RUN_CREATED son atómicos. No hay nuevo ciclo del único.
- Historial paginado con detalle propio por ejecución, copias originales y eventos acotados.
  El listado principal filtra el estado de la ejecución más reciente, no el de ciclos previos.

Pendientes: notificaciones internas. Las fechas y eventos ya pueden consultarse; no se
materializan avisos ni se abre trabajo por cron, fecha, escaneo o traslado.
