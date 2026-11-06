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
  No se calculan aún vencimientos desde cierres reales.
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

Pendientes: tomar, iniciar/reanudar, avanzar, omitir, liberar, completar, cancelar y crear
otra ejecución. No hay cierre ni recurrencia automática en esta entrega.
