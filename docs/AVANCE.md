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
| Concurrencia | Ocho casos con conexiones PostgreSQL simultáneas; conflictos, último admin, traslados e intercambio de ubicaciones |
| Visual | Templates responsive implementados; revisión en navegador pendiente por falta de navegador conectado |
| Despliegue | Configuración y check de seguridad; no se publicó ni validó HTTPS real |
| CI | Workflow incluido; ejecución en GitHub pendiente |
| Otros módulos | No implementados |

Segundo incremento: **116 pruebas aprobadas** (62 previas + 54 nuevas). Migraciones
`assets/0001_initial`, `0002_initial_categories` y `0003_text_length_validation` aplicadas.
HTTP real verificado para los tres roles. No se añadieron dependencias.

Las pruebas y resultados efectivos se registran en PRUEBAS.md. No se presenta revisión
visual simulada ni se afirma validación en el instituto.

Para continuar: leer prompt, README, este archivo y reglas; ejecutar las pruebas
existentes en PostgreSQL antes de modificar. No reemplazar el usuario personalizado,
eliminar migraciones aplicadas ni escribir directamente en datos de otro módulo.
El siguiente incremento lógico sería QR, previa solicitud, reutilizando el UUID público
y la ruta autenticada de ficha. Mantener traslados independientes de mantenimientos.
