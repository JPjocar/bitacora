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
| Recurrencia | Calendario vigente por equipo, propuestas a 7 días, apertura manual de ciclos y tareas limpias |
| Historial de ejecuciones | Lista paginada, detalle por ciclo con copias originales y eventos filtrados |
| Concurrencia | Veintitrés casos PostgreSQL, incluidas apertura duplicada/configuración/cierre/desactivación |
| Visual | Templates responsive implementados; revisión en navegador pendiente por falta de navegador conectado |
| Despliegue | Configuración y check de seguridad; no se publicó ni validó HTTPS real |
| CI | Workflow incluido; ejecución en GitHub pendiente |
| Otros módulos | No implementados |

Sexto incremento: `maintenance/0003_recurring_runs` aplicada sobre siete tablas existentes,
sin columnas ni dependencias nuevas. Roles sincronizados: admin y técnico crean ciclos,
docente sin acceso. El smoke HTTP conserva un periódico sintético con dos ejecuciones,
primera parcial y segunda pendiente con tareas limpias. Resultados en PRUEBAS.md.

**305 pruebas Django aprobadas** (257 previas + 48 nuevas) y **21 pruebas JavaScript**.
Incluye 23 casos concurrentes PostgreSQL y conservación de historial al aplicar 0003.

Las pruebas y resultados efectivos se registran en PRUEBAS.md. No se presenta revisión
visual simulada ni se afirma validación en el instituto.

Para continuar: leer prompt, README, este archivo y reglas; ejecutar las pruebas
existentes en PostgreSQL antes de modificar. No reemplazar el usuario personalizado,
eliminar migraciones aplicadas ni escribir directamente en datos de otro módulo.
Siguiente fase: notificaciones internas. Reutilizar los eventos auditados y el selector
de vencimientos, con clave idempotente por receptor/evento. No implementar dashboard,
incidencias o automatización de apertura sin encargo. La fecha vigente se deriva de la
fecha real más reciente por equipo más el intervalo actual; next_due_date y due_date
de ciclos previos son copias históricas que no se reescriben. Mantener el índice de una
ejecución abierta y las guardias de versión/predecesor al integrar otros módulos.
La reversión de completados y cierres sigue bloqueada; no hay notificaciones todavía.
La revisión visual, cámara física, impresión y despliegue HTTPS siguen pendientes.
