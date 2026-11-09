# Decisiones técnicas

## Ajuste UX/UI autorizado el 08/11/2026

Se centralizan etiquetas y fechas relativas, se agrupa la navegación Bootstrap según
permisos y se enriquece la bandeja en consultas sin alterar sus eventos históricos.
Los vencimientos de la lista resumen obligaciones por equipo con dos lecturas por
página; un trabajo abierto conserva su fecha original. El responsable de una ejecución
cerrada se identifica como histórico. Los reportes HTML reciben celdas de presentación,
mientras CSV mantiene valores simples.

La instrucción posterior del usuario retira puesta en servicio de formularios/ficha/admin,
frente al campo opcional previsto en el maestro. Se conserva la columna nullable y los
eventos existentes para evitar pérdida de información. No se cambian reglas de archivado,
permisos, transiciones ni dependencias. Detalle en [INTERFAZ.md](INTERFAZ.md).

## Decisiones de los incrementos anteriores

Antes del piloto se utilizaba un `CheckboxSelectMultiple` con inventario completo para
inscripciones preventivas. Por solicitud posterior se reemplaza por widget de tarjetas,
modal paginado y selección provisional en DOM con inputs del formulario. La elegibilidad
se extrae a `eligible_devices`; endpoints devuelven HTML acotado, sin API REST ni
almacenamiento de borradores. El QR reutiliza validación y controlador existentes; el
adaptador del escáner se comparte, manteniendo su pantalla anterior. Se rechazan lotes
que exceden 200 en vez de truncarlos, y se descartan respuestas de modales cerrados.
Detalles en [INTERFAZ.md](INTERFAZ.md). Sin modelos, migraciones ni dependencias nuevas.

1. Mantener el monolito Django y PostgreSQL exigidos; proyecto nuevo, sin funcionalidades
   preexistentes que reutilizar o reescribir en la primera entrega. La segunda reutiliza
   accounts, locations y core y agrega assets para dispositivos y movimientos.
2. Usuario extendido de AbstractUser desde el inicio; Groups/Permissions originales para
   roles, sin tabla Role duplicada. Un rol de negocio por cuenta gestionada por los servicios.
3. Roles fijos: Administrador gestiona; Técnico consulta y actualiza estado/observaciones
   de equipos y registra movimientos; Docente consulta ficha limitada de equipos activos
   no retirados. La matriz vigente figura en REGLAS_NEGOCIO.md.
4. Nombres de ubicaciones únicos además de códigos opcionales únicos, para evitar ambientes
   ambiguos. Se documenta como decisión local; no se inventa un catálogo institucional.
5. Desactivación universal de usuarios y ubicaciones en esta entrega. Sin borrado físico.
   Eventos específicos con FK PROTECT en vez de auditoría genérica con IDs sin integridad.
6. Bloqueo del grupo Administrador para serializar mutaciones de cuentas y proteger el
   último administrador. Bloqueo por ubicación y versión optimista en ambos módulos.
7. Django Admin de solo lectura para evitar rutas alternativas que omitan auditoría.
   `createsuperuser`/`changepassword` siguen siendo herramientas internas de recuperación.
8. Bootstrap/HTMX locales, versiones fijas, sin bundler ni Node para el producto.
   HTMX solo en filtros; operaciones persistentes con formularios estándar y PRG.
9. QR/Pillow se incorporan con la fase QR. Chart.js sigue pendiente. Ruff y zxing-cpp
   (decodificador independiente para verificar PNG) solo en desarrollo/pruebas.
10. Clúster PostgreSQL local aislado para comprobar con datos sintéticos, reutilizando
    los binarios instalados sin tocar el servicio existente. No sustituir por SQLite.
11. `.env` se carga únicamente con un lanzador de desarrollo de biblioteca estándar;
    la aplicación desplegada lee variables de entorno, sin dependencia adicional.
12. No se incorpora limitador de login propio en memoria: no sería fiable con varios
    procesos. Se requiere configurar limitación en el proxy antes de exposición pública.
13. Categorías y dispositivos en assets junto a movimientos para garantizar ubicación
    e historial transaccionales. Sin nueva dependencia ni módulo separado redundante.
14. Detalles técnicos de texto libre opcional con ayudas por tipo. Permite describir
    equipos heterogéneos sin columnas RAM/CPU obligatorias o esquemas JSON innecesarios.
15. UUID público para URL estable; código corto criptográficamente aleatorio para búsqueda
    manual. La fase QR ahora codifica la URL de ficha existente sin agregar identificadores.
16. Desactivación separada del estado operativo: archivar es administrativo; retirar del
    control operativo no implica baja patrimonial. Los traslados conservan ambos valores.
17. Movimientos con fecha/hora efectiva no futura y cronología no decreciente. Se rechaza
    insertar retroactivamente entre movimientos ya registrados para no falsear el origen.
18. Bloqueo de destino NO KEY UPDATE permite FKs concurrentes y serializa desactivación.
    Probado con dos equipos intercambiando ubicaciones y con desactivación simultánea.
19. Movimientos cerrados como hechos históricos sin edición o reversión administrativa
    en esta fase. Una corrección de registro erróneo requiere diseñar un flujo posterior;
    no se modifica el historial ni se registra un traslado ficticio para compensarlo.
20. Origen público explícito: nunca construir el QR a partir de Host recibido. Check
    de sintaxis/origen y check de HTTPS para despliegue; localhost solo para desarrollo.
21. Etiquetas HTML imprimibles A4, 62 × 50 mm, QR de 32 mm, margen blanco de cuatro
    módulos, negro sobre blanco. Hasta 100 identificadores y 15 etiquetas por hoja.
    Sin biblioteca PDF ni tabla de lotes. Se requiere calibración física de impresora.
22. html5-qrcode 2.3.8 local y fijado, API de bajo nivel para UI en español. Operaciones
    serializadas y cancelación lógica de callbacks tardíos. Node se usa solo para tests.
23. Permiso explícito de impresión para admin/técnico. Docente conserva consulta y
    escaneo de equipos visibles. Las acciones de lectura no producen eventos de negocio.
24. Fase 6 en maintenance: siete modelos del esquema maestro. La ejecución inicial exige
    copias de participantes/tareas desde esta fase; no supone implementar acciones de fase 7.
    Restricciones de estado inicial y copias de solo lectura hasta habilitar servicios operativos.
25. Meses con calendar.monthrange y ajuste al último día válido, sin dateutil adicional.
    Vencimiento inicial copiado por participante; no fecha global que sustituya sus fechas.
26. Configuración modificable con motivo/versionado; ninguna edición reescribe ejecuciones
    creadas, incluso pendientes. Plantillas antiguas inactivas e inscripciones conservadas.
    No cambia tipo ni fecha prevista del único. No hay reprogramación/cancelación implícita.
27. Administrador configura, técnico consulta y ejecuta desde fase 7, docente sin acceso. Nuevas inscripciones de
    activos no retirados; fuera de servicio permitido, inscritos inactivados se conservan.
    Cada equipo exige al menos una tarea individual aplicable, no necesariamente obligatoria.
28. Límites de piloto: 200 equipos y 50 tareas por configuración. Formset con alta de filas
    por POST, compatible sin JS. No se añadió otra librería/frontend. Tareas copiadas en lotes.
29. UUID de envío y firma de contenido para reintentos; UNIQUE de BD para carreras entre
    selecciones distintas. No es permiso ni identidad pública del mantenimiento.
30. Integración de traslado mediante selector de lectura; confirmar aviso de preventivo
    pendiente no cambia su resultado. Incluye pendiente, asignado y en ejecución desde fase 7.
31. Fase 7 amplía las siete tablas existentes: sin entidad nueva para tareas/notas/eventos.
    ConfiguraciónSnapshot conserva su guardia: save solo admite columnas operativas explícitas.
32. Todas las operaciones bloquean mantenimiento → ejecución y validan versión global.
    Un conflicto entre dos formularios se rechaza para evitar pérdida silenciosa de notas/checks.
33. Tomar solo mediante permiso de técnico. Operar otro responsable exige permiso de
    administración y motivo. Fecha anterior tiene permiso separado, con actor real auditado.
34. Verificación y resumen breve obligatorios al completar; notas y observaciones por
    tarea opcionales. Tareas se guardan por equipo/contexto, sin nota por cada clic.
35. Cálculo siguiente por equipo usa intervalo vigente al completar, serializado contra
    edición administrativa. Es copia histórica; fase 8 incorpora el calendario vigente y ciclos manuales.
36. Registro anterior autorizado admite fecha efectiva anterior al inicio en la aplicación
    para registro extemporáneo; nunca futura. Fecha registrada y primer inicio quedan intactos.
37. Se bloquea reversión de completado/omisión/cierre; no se implementa una corrección
    retrospectiva sin el flujo y pruebas necesarios. Cancelar no invalida equipos completos.
38. RELEASED conserva cada liberación y desde fase 9 produce avisos idempotentes.
    Los ciclos siguientes continúan siendo manuales.
39. Fase 8 reutiliza siete modelos: no tabla calendario, agenda ni jornada. Fecha vigente
    derivada; due_date/next_due_date de participantes conservan sus valores históricos.
40. Calendario anclado a la fecha efectiva más reciente, no al último registro creado.
    Un registro extemporáneo de trabajo antiguo no desplaza uno posterior. Omitidos,
    pendientes y cancelados no reinician calendario. Base solo se usa sin completado previo.
41. Un solo ciclo abierto por mantenimiento, acorde a «después de cerrar, crear siguiente».
    Índice único parcial evita dos aperturas aun con equipos distintos. No se agregan
    flags de estado redundantes por equipo ni restricciones con joins entre tablas.
42. Permiso create_next_run para técnico/admin; solo inscripciones vigentes y equipos activos
    no retirados. Fuera de servicio permitido. Incluir fechas a más de 7 días exige motivo.
    El umbral de propuesta es 7 días civiles de Lima, una decisión local documentada.
43. Versión de configuración + PK del predecesor para rechazar reenvíos. Bloqueos/número único
    protegen concurrencia. No hace falta persistir otro token ni duplicar el identificador.
44. Generador de copias compartido con creación inicial; plantillas actuales según categoría,
    tareas sin marcar y notas vacías. Nueva categoría sin cobertura requiere corregir plantilla.
45. Historial por número, detalle con copias y auditoría filtrada por ciclo. Listado principal
    refleja solo el estado más reciente. Calendario consultado con una query, sin N+1.

46. Fases 9–10: una tabla Notification; exactamente una fuente evento/inscripción.
    No se duplican URL ni padre. Historial retenido y lectura/vigencia independientes.
47. Integración explícita en transacciones de negocio, sin señales, Celery o Redis.
    UNIQUE(receptor,clave) y bloqueo del mantenimiento serializan comando y operaciones.
48. Avisos de fecha por fase de 7 días/hoy/vencido; no ruido diario del mismo vencido.
    Comando periódico materializa y reconcilia; GET permanece libre de escrituras.
    Se omite el aviso opcional al responsable por trabajo iniciado pendiente.
49. Panel sin tablas ni métricas laborales. Exists evita contar N veces el ciclo grupal;
    Subquery comparte ancla real por equipo con recurrencia. Omisión pendiente se decide
    por orden del ciclo, hasta un completado posterior, incluso si otro ciclo está abierto.
50. CSV UTF-8 BOM/`;`, fórmulas neutralizadas y límite de 10 000 sin truncado. Fechas de
    reportes con hora local y offset. HTML imprimible, sin bibliotecas de Excel/PDF.
    Tablas y cifras operativas bastan; no se añade Chart.js sin un gráfico necesario.
51. Únicos no completados/cancelados también muestran y notifican fecha. No generan nuevos
    ciclos automáticos. Desactivar configuración/inscripción/equipo o retirar equipo quita
    la obligación de las proyecciones vigentes, conservando resultados y avisos históricos.

52. Fase 12: una incidencia contiene atención correctiva e historial; dos modelos y ningún
    tipo nuevo de orden. Reutiliza auditoría, roles, formularios Bootstrap y notificaciones.
53. Tres estados y tres resultados: SOLUCIONADA, NO_REPARABLE e INVALIDA_DUPLICADA. Se
    agrupan inválida/duplicada como permite el maestro; no se agrega relación a otro reporte.
54. Técnico toma y atiende; admin supervisa con override y motivo. No reparable requiere
    permiso específico (solo admin por defecto), también concedible expresamente a un
    responsable. Admin puede descartar un pendiente inválido; otros cierres exigen atención.
55. Síntomas originales y cierre retenidos, sin edición del reporte ni reapertura. Un cierre
    equivocado requiere diseñar un flujo correctivo posterior; el MVP bloquea su reversión.
56. Notas técnicas son eventos anexados. Docente ve sus síntomas/estados/resumen de cierre,
    sin notas, motivo o resumen interno de liberación. Puede seguir su caso tras archivar
    el equipo; el acceso a la ficha mantiene el filtro de dispositivos autorizados.
57. UUID del formulario y firma actor/equipo/síntomas para alta idempotente. Versiones y
    bloqueos del padre para acciones; no se confunde síntoma repetido con duplicado automático.
58. Nueva fuente FK de Notification en lugar de otra bandeja o GenericForeignKey; CHECK
    de fuente exclusiva y prefijo incident-event. Recipiente/permiso/propiedad se validan
    antes de listar, contar, leer o abrir. Docente recibe solo sus cierres autorizados.
59. Ficha con historiales de incidencias y preventivos paginados por separado (10 filas),
    respetando permisos. Se reutiliza escáner/código para llegar a Reportar incidencia.
60. Recurrencia correctiva: al menos dos reportes válidos por equipo en fechas de reporte
    del período, excluyendo inválidos/duplicados. No predicción ni clasificación de falla.
    Métricas de abiertos permanecen visibles; período limita cierres y el recuento recurrente.
61. No se actualiza automáticamente estado físico ni recurrencia preventiva. Cambiar estado
    continúa en assets.save_device y exige motivo. Traslado no cierra trabajo correctivo.

62. Fase 11: Waitress 3.0.2 en requirements-pilot (un paquete, cero dependencias nuevas
    transitivas) para WSGI Windows/Linux. No se sustituye el monolito ni se publica runserver.
63. Nginx con TLS, estáticos y límite de POST login real por IP (5/min, ráfaga 10). El proxy
    local limpia/sobrescribe cabeceras; Waitress solo confía en proto de 127.0.0.1. Sin
    confianza global Django ni bloqueo de cuentas. Windows Nginx solo validado para piloto local.
64. Preflight obligatorio, roles/migraciones/estáticos/administrador/origen correctos y PG
    runtime sin superusuario/CREATEDB/CREATEROLE. Migración y backup usan otra cuenta.
65. Un solo archivo de entorno explícito por proceso, sin valores impresos ni secretos
    en argumentos. --allow-demo documenta la excepción de demostración controlada. No
    se instalan servicios/tareas ni se abre una interfaz externa automáticamente.
66. Dos fallos reproducidos antes del arreglo: dashboard devolvía fragmento al restaurar
    historial HTMX y sesión vencida perdía no-store. Se conservan respuesta/cookies/cabeceras;
    no-store abarca login/anónimos y Vary incluye ambas cabeceras de HTMX.
67. CSP solo scripts locales, sin eval; estilos inline por Bootstrap y cámara/img/blob
    permitidos para QR. La revisión real de cámara/Bootstrap/CSP continúa como aceptación manual.
68. Backup custom de PostgreSQL y hashes en el mismo snapshot, media aparte con verificación.
    Restaurar solo en una BD aleatoria nueva, comprobar filas/constraints/secuencias y borrarla;
    nunca aceptar nombre de base fuente o sobrescribir. No tablas extra ni paquetes de backup.
69. Prueba estructural HTML valida IDs/labels en diez rutas; no se presenta como revisión
    responsive o de teclado. Sin navegador conectado, la aceptación manual queda en PILOTO.md.

70. Auditoría aislada detectó avisos para Pillow 12.3.0; se actualiza a 13.0.0, versión
    corregida según upstream, y se repite regresión/QR/auditoría. Con --disable-pip se
    pasa requirements.txt explícitamente junto a los archivos que lo incluyen, comprobando
    cobertura de 12 paquetes del piloto y 13 de desarrollo sin omitidos. No se ocultan avisos.

Fuentes oficiales consultadas para las versiones y APIs utilizadas:

- [Django 5.2: versiones](https://docs.djangoproject.com/en/5.2/releases/), [autenticación](https://docs.djangoproject.com/en/5.2/topics/auth/default/).
- [Checklist de despliegue Django](https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/).
- [django-htmx: instalación](https://django-htmx.readthedocs.io/en/latest/installation.html).
- [HTMX 2: documentación](https://htmx.org/docs/).
- [Bootstrap 5.3: descarga y hashes](https://getbootstrap.com/docs/5.3/getting-started/download/).
- [psycopg 3: instalación](https://www.psycopg.org/psycopg3/docs/basic/install.html).
- [PostgreSQL 18: initdb](https://www.postgresql.org/docs/18/app-initdb.html).
- [Django: transacciones](https://docs.djangoproject.com/en/5.2/topics/db/transactions/) y [select_for_update](https://docs.djangoproject.com/en/5.2/ref/models/querysets/#select-for-update).
- [Python 3.12: secrets](https://docs.python.org/3.12/library/secrets.html).
- [qrcode: API y generación con Pillow](https://pypi.org/project/qrcode/).
- [Pillow: instalación](https://pillow.readthedocs.io/en/stable/installation/basic-installation.html).
- [html5-qrcode: cámara, archivos y cierre](https://scanapp.org/html5-qrcode-docs/docs/apis/classes/Html5Qrcode).
- [ZXing-C++: decodificador independiente para Python](https://github.com/zxing-cpp/zxing-cpp/tree/master/wrappers/python).
- [Django 5.2: formsets, límites, orden y eliminación](https://docs.djangoproject.com/en/5.2/topics/forms/formsets/).
- [Django 5.2: constraints y unicidad con valores nulos](https://docs.djangoproject.com/en/5.2/ref/models/constraints/).
- [Django 5.2: Subquery y OuterRef](https://docs.djangoproject.com/en/5.2/ref/models/expressions/#subquery-expressions).

Las versiones realmente instaladas están fijadas en requirements, sin asumir que sean
las últimas disponibles en futuras fechas. Los cambios futuros deben revisar las fuentes.

Para la infraestructura piloto también se consultaron [Waitress](https://docs.pylonsproject.org/projects/waitress/en/latest/arguments.html),
[Nginx limit_req](https://nginx.org/en/docs/http/ngx_http_limit_req_module.html),
[Nginx Windows](https://nginx.org/en/docs/windows.html),
[pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html) y
[pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html). Detalle en PILOTO.md.
