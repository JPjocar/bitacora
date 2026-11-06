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

**Técnico:** consulta listado/detalle de ubicaciones y su perfil. No administra cuentas,
roles ni ubicaciones. **Docente:** en esta fase solo dispone de su perfil; los equipos e
incidencias serán módulos posteriores.

Si aparece «otra persona modificó…», recargue, revise los datos actuales y vuelva a
realizar la edición. No basta con reenviar el formulario anterior. Un error de validación
mantiene los datos para corregirlos. Los enlaces de lista permiten volver al contexto.

**Responsable técnico:** ejecutar migrate y sync_roles al instalar. Crear superusuario
interactivamente para habilitar el primer administrador. Consultar README para pruebas
y documentación de seguridad antes de cualquier despliegue.
