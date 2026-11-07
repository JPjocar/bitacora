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
