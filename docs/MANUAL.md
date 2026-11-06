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
