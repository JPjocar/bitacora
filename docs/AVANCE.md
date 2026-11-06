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
| Primera ejecución | Pendiente, sin asignación ni inicio, copias de equipos/fechas/tareas conservadas |
| Ejecución y recurrencia operativas | Toma, inicio, avances, omisión, liberación, cierre y siguientes ciclos pendientes |
| Concurrencia | Once casos PostgreSQL: incluye reenvío de creación y edición preventiva concurrente |
| Visual | Templates responsive implementados; revisión en navegador pendiente por falta de navegador conectado |
| Despliegue | Configuración y check de seguridad; no se publicó ni validó HTTPS real |
| CI | Workflow incluido; ejecución en GitHub pendiente |
| Otros módulos | No implementados |

Cuarto incremento: **197 pruebas Django aprobadas** (145 previas + 52 nuevas) y
**21 pruebas JavaScript**. Migración `maintenance/0001_initial` aplicada: siete modelos,
sin alterar migraciones previas. Roles sincronizados; admin configura, técnico consulta,
docente sin acceso. HTTP real verificado para los tres roles. Sin dependencias nuevas.
Demo preventiva explícita e idempotente, con un único y un periódico pendientes.

Las pruebas y resultados efectivos se registran en PRUEBAS.md. No se presenta revisión
visual simulada ni se afirma validación en el instituto.

Para continuar: leer prompt, README, este archivo y reglas; ejecutar las pruebas
existentes en PostgreSQL antes de modificar. No reemplazar el usuario personalizado,
eliminar migraciones aplicadas ni escribir directamente en datos de otro módulo.
Siguiente fase: ejecución y avances preventivos. Al habilitarla, ampliar las restricciones
de estado inicial y el manager de copias únicamente mediante servicios validados, con
pruebas de toma/inicio/liberación/cierre. Actualizar el selector de aviso de traslados para
los estados nuevos. No implementar recurrencia futura o notificaciones sin encargo.
La revisión visual, cámara física, impresión y despliegue HTTPS siguen pendientes.
