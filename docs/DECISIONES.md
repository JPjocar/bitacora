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
9. No instalar QR/Pillow/Chart.js antes del módulo que los necesite. Ruff solo en desarrollo.
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
    manual. El UUID aún no se codifica en QR: esa fase no se solicitó.
16. Desactivación separada del estado operativo: archivar es administrativo; retirar del
    control operativo no implica baja patrimonial. Los traslados conservan ambos valores.
17. Movimientos con fecha/hora efectiva no futura y cronología no decreciente. Se rechaza
    insertar retroactivamente entre movimientos ya registrados para no falsear el origen.
18. Bloqueo de destino NO KEY UPDATE permite FKs concurrentes y serializa desactivación.
    Probado con dos equipos intercambiando ubicaciones y con desactivación simultánea.
19. Movimientos cerrados como hechos históricos sin edición o reversión administrativa
    en esta fase. Una corrección de registro erróneo requiere diseñar un flujo posterior;
    no se modifica el historial ni se registra un traslado ficticio para compensarlo.

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

Las versiones realmente instaladas están fijadas en requirements, sin asumir que sean
las últimas disponibles en futuras fechas. Los cambios futuros deben revisar las fuentes.
