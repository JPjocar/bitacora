# Decisiones técnicas

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
27. Administrador configura, técnico consulta, docente sin acceso. Nuevas inscripciones de
    activos no retirados; fuera de servicio permitido, inscritos inactivados se conservan.
    Cada equipo exige al menos una tarea individual aplicable, no necesariamente obligatoria.
28. Límites de piloto: 200 equipos y 50 tareas por configuración. Formset con alta de filas
    por POST, compatible sin JS. No se añadió otra librería/frontend. Tareas copiadas en lotes.
29. UUID de envío y firma de contenido para reintentos; UNIQUE de BD para carreras entre
    selecciones distintas. No es permiso ni identidad pública del mantenimiento.
30. Integración de traslado mediante selector de lectura; confirmar aviso de preventivo
    pendiente no cambia su resultado. Fase 7 debe incluir los nuevos estados en ese selector.

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

Las versiones realmente instaladas están fijadas en requirements, sin asumir que sean
las últimas disponibles en futuras fechas. Los cambios futuros deben revisar las fuentes.
