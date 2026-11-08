# Ajustes de interfaz · 8 de noviembre de 2026

Encargo posterior al piloto: simplificar dispositivos, unificar estados, dar contexto
a los avisos y hacer visibles responsables y vencimientos. No cambia permisos,
transiciones, reglas de archivado ni la arquitectura del monolito.

## Dispositivos

Se retira **Puesta en servicio** de creación, edición, ficha y administración técnica.
Los formularios tampoco aceptan modificarla mediante un POST construido manualmente.
Se conserva la columna nullable `Device.commissioned_on`, sus validaciones históricas
y los eventos anteriores para no borrar datos existentes. No se crea migración.
No interviene en el cálculo preventivo. La adquisición sigue siendo opcional.
Esta decisión reemplaza la recomendación del maestro de exponer ambas fechas.

## Estados y fechas

`apps/core/templatetags/ui.py` y los componentes `status_badge.html` / `deadline.html`
centralizan la presentación con utilidades Bootstrap locales. Las etiquetas tienen
texto, fondo suave, borde y esquinas redondeadas; no dependen únicamente del color.

| Significado | Color |
| --- | --- |
| Activo, operativo, completado, solucionada | Verde |
| Inactivo, fuera de servicio, no reparable, vencido | Rojo |
| Observaciones, pendiente, parcial, vencimiento hasta 7 días | Ámbar |
| Asignado / trabajo en curso | Azul claro / azul |
| Retirado, omitido, cancelado, cerrada, inválida/duplicada | Gris |

Se aplican en listas y fichas de usuarios, ubicaciones, categorías y dispositivos;
ejecuciones, resultados, tareas e historial preventivo; incidencias e historial del
dispositivo; avisos, panel y reportes HTML imprimibles. Los filtros y selectores de
formularios conservan controles nativos. El contador de avisos distingue cantidades.
En impresión se conservan bordes y texto oscuro, aun sin imprimir fondos.

Las fechas muestran `dd/mm/aaaa` y una etiqueta **Hoy**, **Mañana**, **En N días**
o **Vencido hace N días**, usando el día civil de Lima. Son señales temporales de
presentación, no nuevos estados persistidos. Un resultado histórico completado
conserva su fecha original sin presentarse como trabajo vencido pendiente.

## Navegación

- La marca **Bitacora** vuelve al inicio; **Panel** queda visible para quienes tienen acceso.
- **Equipos** agrupa Dispositivos, Escanear QR, Movimientos y Categorías según permisos.
- **Mantenimientos** e **Incidencias** mantienen acceso directo.
- **Administración** agrupa Ubicaciones, Usuarios y Roles según permisos.
- Perfil, Avisos y Salir permanecen disponibles; no se muestran menús vacíos.
- Dispositivos ofrece también un botón **Escanear QR**.

Se reutilizan el collapse responsive y los dropdowns Bootstrap existentes, sin nuevo
framework ni JavaScript propio. La sección actual se destaca; el menú usa botones
con `aria-expanded` y listas asociadas. No modifica las comprobaciones de servidor.

## Avisos

La bandeja añade contexto obtenido después de filtrar avisos por receptor y permisos:
tipo/código/nombre y ubicación actual del equipo; síntomas públicos de incidencias
normalizados y limitados a 160 caracteres con elipsis; cantidad y hasta tres tipos
para preventivos grupales, con una muestra breve de equipos.

El contenido histórico del aviso y las claves idempotentes se conservan. Esto permite
enriquecer avisos existentes sin migrarlos ni reescribirlos. Nunca se consultan notas
técnicas internas para construir un extracto. Los textos siguen escapados por Django.
El botón distingue **Ver incidencia**, **Ver mantenimiento** y **Ver vencimiento**.
Abrir y marcar leído conserva el POST con CSRF; consultar la bandeja no escribe.
Las relaciones se cargan por página con `select_related` y `Prefetch`, sin una consulta
adicional por aviso o equipo.

## Lista de mantenimientos

Se añade una columna **Responsable**, con nombre completo y fallback al usuario.
Sin responsable se indica **Sin asignar**. Si la ejecución está cerrada, se aclara
**Última ejecución cerrada**, sin presentarla como una asignación actual.

**Vencimiento pendiente más próximo** resume las obligaciones por equipo y muestra
la fecha más antigua, cantidad de equipos y cantidad vencida. No sustituye los
calendarios individuales. `maintenance.selectors.list_schedules` hace dos consultas
por página y reutiliza los selectores y el cálculo de recurrencia existentes:

1. Trabajo abierto sin finalizar: fecha original de su participación, incluso si se
   modificó la configuración o se archivó después el dispositivo/inscripción.
2. Las demás obligaciones vigentes: última realización válida más intervalo actual,
   o fecha base más intervalo. Los omitidos mantienen su vencimiento.
3. Mantenimiento único completado/cancelado: no anuncia otro vencimiento.
4. Una configuración con fechas fuera de rango se señala para revisión; no se presenta
   silenciosamente como completa ni se recalculan datos históricos.

## Verificación y límites

Casos automatizados en `tests/test_ui.py`; regresión y comandos observados en
[PRUEBAS.md](PRUEBAS.md). No hay dependencias ni migraciones nuevas.
El navegador de la sesión no está disponible (selección fallida y lista vacía).
La estructura HTML se comprueba automáticamente; quedan por comprobar visualmente
los dropdowns, foco/teclado, contraste efectivo y anchos 1366/390 px con navegador real.
No se afirma validación visual, impresión física ni prueba de cámara.

Referencias: [Bootstrap dropdowns](https://getbootstrap.com/docs/5.3/components/dropdowns/),
[navbar responsive](https://getbootstrap.com/docs/5.3/components/navbar/),
[badges](https://getbootstrap.com/docs/5.3/components/badge/) y
[W3C: uso del color](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html).
