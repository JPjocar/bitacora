# Avance al 6 de noviembre de 2026 (Lima)

| Área | Estado |
| --- | --- |
| Base de proyecto | Django, PostgreSQL, entorno, Git local, dependencias fijas, templates y estáticos |
| Usuarios | Login/logout, perfil, alta/edición/desactivación/reactivación, contraseña y auditoría |
| Roles | Tres grupos fijos, permisos, asignación por cuenta y consulta de matriz |
| Ubicaciones | Tipos, listado/detalle, filtros/paginación, alta/edición/desactivación/reactivación |
| Categorías | Catálogo inicial de seis tipos, alta/edición/desactivación e historial |
| Dispositivos | Ficha, serie opcional, código inmutable, búsqueda/filtros, fechas, archivo y consulta limitada docente |
| Movimientos | Traslados físicos con origen real, motivo, fechas, advertencia y actualización atómica de ubicación |
| QR | PNG por UUID, origen explícito, sesión y permisos por equipo |
| Etiquetas | Individuales/selección, deduplicación, A4; prueba física pendiente |
| Escáner | Cámara en modal, imagen local y código manual; pruebas JS simuladas, cámara real pendiente |
| Configuración preventiva | Único/periódico, equipos, tareas, fechas, edición/desactivación y auditoría |
| Ejecución preventiva | Seis estados, toma, inicio/reanudación, avances/notas, liberación, omisión, completado y cierre/cancelación |
| Fechas reales | Por equipo, registro anterior administrativo con motivo, cierre general independiente |
| Recurrencia | Próxima fecha calculada al completar equipo; siguientes ciclos pendientes |
| Concurrencia | Dieciocho casos PostgreSQL: toma, inicio, avance/liberación, omisión/completado, cierre/rectificación y configuración/fecha |
| Visual | Templates responsive implementados; revisión en navegador pendiente por falta de navegador conectado |
| Despliegue | Configuración y check de seguridad; no se publicó ni validó HTTPS real |
| CI | Workflow incluido; ejecución en GitHub pendiente |
| Otros módulos | No implementados |

Quinto incremento: migración `maintenance/0002_execution_workflow` aplicada sobre las
siete tablas existentes, sin reescribir migraciones previas. Roles sincronizados: técnico
ejecuta su trabajo; admin interviene con motivo; docente sin acceso. HTTP real incluye
liberación/reanudación y cierre parcial de un registro sintético conservado. Sin nuevas
dependencias. Resultados efectivos de regresión y migración en PRUEBAS.md.

**257 pruebas Django aprobadas** (197 previas + 60 nuevas) y **21 pruebas JavaScript**.
Incluye dieciocho casos concurrentes PostgreSQL y conservación de datos de fase 6 al migrar.

Las pruebas y resultados efectivos se registran en PRUEBAS.md. No se presenta revisión
visual simulada ni se afirma validación en el instituto.

Para continuar: leer prompt, README, este archivo y reglas; ejecutar las pruebas
existentes en PostgreSQL antes de modificar. No reemplazar el usuario personalizado,
eliminar migraciones aplicadas ni escribir directamente en datos de otro módulo.
Siguiente fase: recurrencia y apertura manual de ciclos. Ampliar la restricción actual
de número 1, impedir participantes duplicados en ciclos abiertos y crear tareas limpias.
Usar fecha real de cada equipo completado y conservar vencimientos de omitidos. La copia
next_due_date registra el cálculo al completar: si cambia luego el intervalo, la fase de
recurrencia debe derivar fechas futuras con la configuración vigente sin reescribir historia.
No hay reversión de equipos completados, ciclos siguientes ni notificaciones todavía.
La revisión visual, cámara física, impresión y despliegue HTTPS siguen pendientes.
