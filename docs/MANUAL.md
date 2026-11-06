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

Al guardar verá la primera ejecución pendiente con equipos, fechas y tareas. Todavía no
hay acciones para tomar, iniciar, avanzar o cerrar. El técnico puede consultar esta pantalla
e historial; el docente no tiene acceso al módulo.

**Editar configuración:** explique el motivo. La ejecución conserva equipos, fechas y
tareas originales, aunque siga pendiente. En periódicos, cambiar base/intervalo configura
futuros ciclos, cuya creación pertenece a otra fase. El único no permite cambiar fecha
prevista ni generar otra ejecución. Desactivar conserva historia y no cancela. Si otro
usuario editó antes, recargue y revise antes de guardar nuevamente.

Desde la ficha de equipo, Ver mantenimientos filtra por su código. Trasladar un equipo
con preventivo pendiente muestra advertencia y pide confirmación: no completa, omite
ni cambia el vencimiento preventivo.
