# Manual breve

**Todas las cuentas:** ingrese con su usuario y contraseña. En el nombre de usuario del
menú abra **Mi perfil** para revisar sus datos o cambiar la contraseña usando la actual.
**Salir** cierra la sesión. Si olvidó la contraseña, solicite restablecimiento al administrador.

**Administrador:** en **Usuarios**, filtre por nombre/usuario, rol y estado. Abra una
cuenta para ver datos e historial. **Nuevo usuario** solicita usuario, rol y contraseña
confirmada; nombres y correo son opcionales. **Editar usuario** permite cambiar datos,
rol y casilla Activo. Desmarcar Activo impide futuros accesos sin borrar información.
Marcarlo reactiva la cuenta. No se permite desactivar la cuenta propia o cambiar el rol propio.
Para otra cuenta use **Restablecer contraseña** y comunique la nueva clave por un medio
autorizado; el usuario debe cambiarla desde su perfil. No envía correos automáticamente.

**Roles:** muestra los permisos reales de los tres roles. No permite inventar roles ni
conceder privilegios técnicos. El rol se asigna al editar una cuenta.

**Ubicaciones:** busque por nombre o código y filtre tipo/estado. **Nueva ubicación**
solicita nombre y tipo; código y descripción son opcionales. Abra el nombre para consultar
detalle. En **Editar ubicación**, desmarque Activo para desactivar o márquelo para reactivar.
Los cambios aparecen en el historial con actor y hora de Lima.

**Dispositivos (administrador):** entre a Dispositivos → Nuevo dispositivo. Seleccione
nombre, categoría y ubicación inicial activa. Complete opcionalmente marca/modelo,
serie, detalles y fechas. El código se genera al guardar y no se puede editar.
En la ficha, Editar permite modificar datos y desactivar/reactivar el registro. Para
cambiar el estado operativo indique un motivo. Para cambiar ubicación use Registrar traslado.
En Categorías puede crear, editar o desactivar categorías conservando equipos existentes.

**Técnico:** consulta ubicaciones y fichas de dispositivos. En Actualizar estado puede
cambiar estado/observaciones, con motivo si cambia el estado. No puede editar datos de
identificación ni archivar equipos. Tanto técnico como administrador pueden registrar
traslados y consultar movimientos.

**Registrar traslado:** abra la ficha del equipo, compruebe el origen mostrado, seleccione
destino, motivo y fecha/hora efectiva en Lima. Registre solo traslados físicos ya realizados.
Si aparece una advertencia por equipo fuera de servicio, retirado o inactivo, léala y
confirme. El traslado no repara el equipo. Al guardar verá el evento histórico y la ficha
tendrá nueva ubicación. No hay solicitudes, aprobaciones ni recepciones pendientes.

**Movimientos:** filtre por nombre/código del equipo, origen/destino o rango de fechas
efectivas. Abra un resultado para ver motivo, autor, fechas y observaciones. Un historial
no es editable; si detecta un error, comuníquelo al responsable, sin inventar traslados.

**Docente:** consulta su perfil y fichas limitadas de equipos activos no retirados. Puede
buscar por código o nombre y filtrar categoría, ubicación o estado. No accede a números
de serie, detalles técnicos, notas internas ni movimientos. Incidencias es una fase posterior.

Si aparece «otra persona modificó…», recargue, revise los datos actuales y vuelva a
realizar la edición. No basta con reenviar el formulario anterior. Un error de validación
mantiene los datos para corregirlos. Los enlaces de lista permiten volver al contexto.

**Responsable técnico:** ejecutar migrate y sync_roles al instalar. Crear superusuario
interactivamente para habilitar el primer administrador. Consultar README para pruebas
y documentación de seguridad antes de cualquier despliegue.

**Imprimir QR (administrador o técnico):** abra la ficha → Imprimir etiqueta. Para varias,
marque las casillas de Dispositivos y pulse Imprimir seleccionados. La selección solo
abarca la página visible y se pierde al cambiar filtros/página. En la vista previa espere
«Etiquetas listas», pulse Imprimir y elija A4 vertical, escala 100 %, sin encabezados/pies
del navegador. El formato es 62 × 50 mm, hasta 15 etiquetas por hoja. Compruebe una hoja
real: el código completo y el margen blanco alrededor del QR deben verse sin recortes.
Nombre/categoría se abrevian; el código nunca se abrevia. No hay lotes de mantenimiento.

**Escanear (los tres roles):** desde Escanear QR pulse Abrir cámara, conceda permiso y
apunte al QR completo. Cerrar cámara detiene la captura. También puede seleccionar una
imagen PNG/JPG/WebP de hasta 10 MB, procesada localmente, o escribir el código de etiqueta
(se aceptan minúsculas y espacios periféricos). Solo se abrirá una ficha disponible para
su cuenta. Un QR externo o equipo inexistente/no autorizado muestra un error.

Con la cámara habitual del teléfono, abra el enlace detectado: si falta sesión, ingrese
y volverá a la ficha. Dentro de Bitacora, permiso denegado, cámara ausente/ocupada o falta
de HTTPS muestran alternativas de imagen/código. Libere la cámara de otras aplicaciones
o conceda permiso en el navegador y vuelva a abrir el modal. Sin JavaScript puede buscar
manualmente. Una IP local con HTTP normalmente no habilita cámara integrada.

**Origen de etiquetas:** configure BITACORA_PUBLIC_URL antes de imprimir para uso real.
El localhost predeterminado solo abre la instancia en esa computadora. Un teléfono
necesita un origen alcanzable y HTTPS configurado. Reinicie el servidor tras cambiar
el entorno. Cambiar el dominio afecta los QR ya impresos: conserve el origen anterior
mediante redirección controlada o reimprima. No use el dominio de ejemplo de los checks.

**Preventivos (administrador):** Mantenimientos → Nuevo mantenimiento. Elija Único o
Periódico antes de llenar campos; cambiar tipo abre un formulario nuevo. Indique nombre,
descripción opcional y equipos. Único pide fecha prevista; Periódico pide fecha base e
intervalo en días/meses. La fecha base no significa mantenimiento realizado.

Configure tareas verificables. «Por dispositivo» crea una copia independiente para cada
equipo, opcionalmente limitada a su categoría. «General de la ejecución» se incluye una
vez y no admite categoría. Cada equipo necesita al menos una tarea individual aplicable.
Marque obligatoria/opcional, indique orden y use Agregar otra tarea si necesita más filas.
Agregar filas no guarda; para quitar una tarea marque Eliminar y después guarde. Límites:
200 equipos y 50 tareas. No se usa una pantalla separada para grupos.

Al guardar verá la primera ejecución pendiente con equipos, fechas y tareas. El técnico
puede tomarla y trabajar desde esa pantalla. El docente no tiene acceso al módulo.

**Editar configuración:** explique el motivo. La ejecución conserva equipos, fechas y
tareas originales, aunque siga pendiente. En periódicos, cambiar base/intervalo configura
los siguientes ciclos manuales. El único no permite cambiar fecha
prevista ni generar otra ejecución. Desactivar conserva historia y no cancela. Si otro
usuario editó antes, recargue y revise antes de guardar nuevamente.

Desde la ficha de equipo, Ver mantenimientos filtra por su código. Trasladar un equipo
con preventivo pendiente muestra advertencia y pide confirmación: no completa, omite
ni cambia el vencimiento preventivo.

**Ejecutar (técnico):** abra un mantenimiento pendiente y confirme Tomar mantenimiento.
Queda Asignado, todavía sin inicio. Pulse Iniciar mantenimiento cuando empiece físicamente.
En Registrar avance marque las tareas realizadas y guarde; las observaciones por tarea y
notas del equipo son opcionales. En grupos, registre aparte las tareas generales. Otro
técnico puede consultar, pero no guardar avances del responsable actual.

**Liberar y continuar:** Liberar mantenimiento pide qué se hizo y por qué se libera. Se
conservan checks, notas y primer inicio. Queda disponible sin responsable. Quien lo tome
debe pulsar Reanudar mantenimiento antes de continuar. Cada liberación y reanudación se
consulta en Historial de cambios; no hay liberación por computadora.

**Completar equipo:** compruebe sus tareas obligatorias, confirme la verificación final
y escriba un resumen breve. Se registra hoy en Lima, de forma independiente para cada
equipo. Una fecha anterior solo la registra una cuenta autorizada, con motivo. El sistema
no admite fechas futuras ni modificar el resultado una vez completado.

**Omitir de esta ejecución:** cuando el equipo no será atendido en ese trabajo, indique
motivo. Permanece en historia y conserva vencimiento; no cuenta como mantenido. El traslado
físico no sustituye esta acción ni altera sus tareas.

**Cerrar mantenimiento:** primero complete u omita cada equipo y termine las tareas generales
obligatorias. Todos completados producen cierre total; completados y omitidos, parcial.
Todos omitidos no permiten parcial: use Cancelar mantenimiento, con motivo. Cancelar no
se permite si ya hay equipos completos. El cierre general registra fecha/hora propia.

**Intervención administrativa:** el administrador puede actuar con motivo sobre una
ejecución de otro responsable, incluso liberar al responsable desactivado. No toma como
técnico. Los cambios quedan a nombre del actor real. No hay reversión de completados o
cierres. Los cambios excepcionales requieren motivo y quedan auditados.

**Vencimientos por equipo:** desde el detalle del mantenimiento periódico abra esa opción.
La tabla muestra última fecha real completada, vencimiento vigente, situación temporal y
disponibilidad. Filtre por código/nombre o vencido/hoy/próximo/posterior. Próximo significa
7 días. Un equipo omitido sigue con su fecha anterior; otro completado calcula su propia
fecha. El enlace de última ejecución permite comprobar el trabajo que sirve como ancla.

**Crear siguiente ejecución (técnico o administrador):** cierre o cancele la actual y
abra Crear siguiente ejecución. Se marcan como propuesta los equipos vencidos o próximos.
Revise códigos/fechas y seleccione las inscripciones vigentes que atenderá; si incluye
otros equipos con fecha posterior, explique el motivo. No se incluyen inactivos/retirados.
Al confirmar verá una nueva ejecución pendiente, sin técnico ni inicio y con tareas limpias.
Tomar e Iniciar siguen siendo acciones posteriores explícitas. No hay apertura automática.

Si aparece un conflicto de configuración/predecesor, recargue: pudo cambiar el intervalo
o crearse otro ciclo. No basta con reenviar. Solo puede haber una ejecución abierta del
mismo mantenimiento, aunque seleccione equipos distintos. El mantenimiento único no tiene
esta acción. Un cambio de categoría del equipo puede exigir actualizar sus tareas primero.

**Historial de ejecuciones:** lista números, estados, conteos y fechas. Abra una ejecución
para ver sus datos originales, tareas, notas y resultados. Eventos de esta ejecución filtra
la auditoría para ese ciclo. Volver a la ejecución más reciente no modifica el historial.
Las fechas congeladas del trabajo pueden diferir de los vencimientos vigentes si después
cambió la configuración; ambos datos tienen una finalidad distinta.

## Avisos internos y panel

Administrador y técnico encuentran **Avisos** y **Panel** en la navegación. El docente
accede a su bandeja de cierres de incidencias, sin panel ni exportaciones. El contador consulta solo sus
avisos vigentes sin leer cada 30 segundos; no hay correo, SMS ni notificaciones fuera de la app.
La bandeja ofrece sin leer/vigentes, leídas, resueltas y todas, con 20 filas por página.
**Ver mantenimiento y marcar leída** abre el ciclo o calendario original mediante POST;
la simple consulta no marca leído. **Marcar vigentes como leídas** solo afecta su cuenta.

Cada alta, nuevo ciclo y liberación avisa inmediatamente a técnicos/administradores
activos autorizados. Tomar el trabajo resuelve el aviso de disponibilidad anterior.
Las fechas se materializan con el siguiente comando, desde la raíz del repositorio:

```powershell
.\.venv\Scripts\python.exe scripts/manage_local.py generate_notifications
```

Es seguro repetirlo: no duplica evento/receptor ni genera un vencido nuevo cada día.
Actualiza avisos próximos a 7 días, para hoy y vencidos, y resuelve fechas que ya no
corresponden. Recalcula desde la fecha real individual y configuración vigente. Si
no se ejecuta, **no aparecen nuevos avisos de fecha ni se retiran los obsoletos**;
los de disponibilidad/liberación siguen siendo inmediatos. Consulte el calendario
del recurso para ver el estado actual. La lectura se conserva si vuelve la misma clave.

**Programación piloto Windows (pendiente de activar en el equipo que lo alojará):**
en Programador de tareas cree una tarea con repetición cada hora e inicio diario.
Programa: ruta absoluta `C:\Users\jpjoc\Desktop\bitacora\.venv\Scripts\python.exe`.
Argumentos: `scripts/manage_local.py generate_notifications`.
Iniciar en: `C:\Users\jpjoc\Desktop\bitacora`. Use una cuenta autorizada para leer el
`.env` y conectar a la base, sin poner credenciales en argumentos. Configure no iniciar
otra instancia si sigue en ejecución y revise resultado 0; un fallo de fechas devuelve
código no cero e identifica el mantenimiento. La base y el equipo deben estar encendidos.
No se instaló una tarea del sistema durante esta entrega. El despliegue real debe usar
sus propias rutas/configuración; no copie la cuenta ni credenciales demo.

En **Panel**, seleccione ubicación, tipo, estado del equipo, activos/archivados,
estado de ejecución, período o código/nombre. Aplique filtros y elija la tabla:
vencimientos ordenados, ejecuciones, sin preventivo periódico, omisiones o inventario.
Inventario cuenta equipos; prevención cuenta pares equipo–preventivo. Un ciclo grupal
cuenta una vez. El período afecta vencimientos, fecha de omisión y cierre (Lima),
manteniendo visible el trabajo abierto. El estado de ejecución no restringe inventario.
Las tablas tienen paginación del servidor y siguen funcionando sin JavaScript.

**Exportar CSV** descarga la tabla filtrada completa hasta 10 000 filas, UTF-8 con BOM
y separador punto y coma. **Versión imprimible** ofrece los mismos datos y filtros;
use Imprimir del navegador. Las fechas con hora incluyen el huso de Lima. Si supera el
límite, reduzca filtros; no se recortan filas. Si hay una fecha preventiva inválida,
el panel muestra el recurso a revisar y bloquea CSV para evitar exportaciones incompletas.
El panel incluye incidencias y recurrencia de reportes, sin rendimiento individual de técnicos.

## Incidencias y atención correctiva

**Reportar (docente, técnico o administrador):** busque el equipo con el escáner existente
(cámara, archivo o código manual), abra su ficha y seleccione **Reportar incidencia**.
Compruebe código/nombre/ubicación y describa síntomas. No incluya contraseñas ni datos
personales. El reporte queda pendiente y avisa a técnicos y administradores. No cambia
el estado operativo ni registra un preventivo. No se reporta sobre equipos archivados
o retirados. Reenviar el mismo formulario devuelve el mismo reporte; para una falla
distinta, abra un formulario nuevo. No hay deduplicación automática por síntomas.

**Seguimiento docente:** Incidencias muestra únicamente sus reportes, incluso si el
equipo se archiva después. Filtre por código/nombre/síntomas, estado, resultado, tipo,
ubicación o fechas de reporte (Lima). El detalle muestra estado y resumen final; las
notas técnicas, motivos y resúmenes de liberación son internos. Al cerrar recibe un
aviso propio, con resultado Solucionada, No reparable o Inválida o duplicada. El resumen
de cierre es visible para el reportante: escriba solo información que corresponda compartir.

**Atender (técnico):** abra un pendiente y confirme **Tomar incidencia**. La toma es
exclusiva y pasa directamente a En atención; no hay inicio separado ni cronómetros.
Puede registrar notas técnicas opcionales. **Liberar incidencia** exige motivo y resumen
breve de lo hecho/pendiente, quita la asignación, conserva notas y avisa de nuevo.
Otro técnico podrá tomarla y continuar desde su historial, sin una reasignación formal.

**Cerrar:** el responsable elige Solucionada o Inválida o duplicada y escribe resumen
obligatorio. **No reparable** requiere permiso específico y motivo; por defecto solo lo
tiene el administrador. Una avería no reparable queda cerrada con ese resultado, nunca
se presenta como solucionada. El administrador puede intervenir con justificación; puede
descartar un reporte inválido pendiente sin asignarlo a un técnico. Para los otros
resultados el caso debe estar en atención. El cierre se conserva y no se reabre/rectifica
en este MVP. Si recibe conflicto de versión, recargue y revise antes de repetir.

El estado físico se actualiza por **Actualizar estado del equipo**, con su servicio y
motivo habituales. No se infiere desde el cierre de incidencia. Trasladar el equipo no
cierra/libera la incidencia y corregir una falla no altera tareas ni fechas preventivas.

La ficha integra auditoría física, incidencias y ejecuciones preventivas con paginación
independiente (10 filas por historial nuevo). El docente ve sus incidencias y la ficha
limitada autorizada; nunca el historial preventivo ni casos ajenos. Las listas de
incidencias tienen 20 filas y funcionan con o sin HTMX.

El panel añade tablas/reportes **Incidencias** y **Equipos con incidencias recurrentes**.
El estado de incidencia solo filtra ese módulo. El período filtra cierres manteniendo
abiertos visibles; para recurrencia cuenta fechas de reporte: al menos dos por equipo,
excluyendo inválidos/duplicados. Es una consulta histórica, sin diagnóstico ni predicción.
