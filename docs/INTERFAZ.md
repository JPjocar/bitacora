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

## Selector de equipos en mantenimientos

La lista completa de checkboxes de creación/edición se sustituye por una cuadrícula.
La primera tarjeta es **+ Agregar equipos**; cada equipo nuevo aparece inmediatamente
a su derecha y desplaza los anteriores. Se muestra código, nombre, categoría, ubicación
y estado, con acción **Quitar**. Duplicados no crean otra tarjeta ni alteran el orden.
Los cambios son una selección provisional hasta guardar el mantenimiento.

El único modal contiene búsqueda por nombre, código o ubicación, filtro de ubicación
y páginas de **20 equipos**. La selección permanece entre páginas, filtros y aperturas.
**Agregar todos los filtrados** incluye todas las coincidencias, no solo la página visible.
El servidor entrega como máximo 200 tarjetas; si el filtro excede ese límite, pide
acotarlo. Si la unión con la selección actual supera 200, el cliente rechaza el lote
completo. El campo y el servicio vuelven a validar el límite al guardar.

La sección QR del mismo modal acepta código o URL de etiqueta, cámara explícita e imagen
PNG/JPEG/WebP de hasta 10 MB. Se reutilizan `resolve_scan`, `qr-controller.js` y el adaptador
compartido `BitacoraScanner.bind`, extraído del escáner existente. No se anidan modales.
La imagen se decodifica localmente; únicamente se consulta su texto, sin subir el archivo.
El texto leído siempre se valida en Django: no se navega al contenido del QR.
El resultado agrega directamente el equipo y anuncia su identidad; la cámara se puede
reiniciar para el siguiente. Cerrar modal/sección QR, ocultar o abandonar la página y
enviar el formulario detienen el lector. Respuestas de una apertura anterior se descartan.

`eligible_devices` concentra la elegibilidad del campo y del selector: activos no
retirados, más inscripciones vigentes ya existentes en edición, con la visibilidad del
actor. Buscar/agregar al borrador requiere permiso de crear/editar mantenimiento; el
GET no modifica datos. El guardado sigue en el servicio transaccional anterior.
Cambiar inscripciones no altera las participaciones de una ejecución ya creada.

El widget solo consulta las tarjetas seleccionadas, conservando su orden del POST.
No enumera el inventario para construir opciones. Agregar tareas o corregir validaciones
conserva esa selección. Sin JavaScript se puede agregar por código y quitar tarjetas
mediante POST con CSRF, conservando campos/tareas y sin guardar el mantenimiento.
No se persiste el orden en la base de datos ni se crea un borrador o sesión adicional.

Archivos principales de este selector:

| Capa | Archivos |
| --- | --- |
| Campo y widget | `apps/maintenance/forms.py`, `widgets.py` |
| Consulta y endpoints HTML | `selectors.py`, `picker_views.py`, `views.py`, `urls.py` en maintenance |
| Plantillas | `maintenance/form.html`, `device_picker_modal.html`, `device_card.html`, `picker_results.html`, `picker_selection.html`, `widgets/device_grid.html` |
| Renderizado compartido | `templates/components/form_fields.html` permite excluir el campo de la sección genérica |
| Interacciones | `static/js/device-picker.js`, adaptador compartido `scanner.js` y `static/css/maintenance.css` |
| Pruebas | `tests/test_device_picker.py`, `tests/js/device-picker.test.cjs`, `tests/js/scanner.test.cjs`, `scripts/smoke_http.py` |

## Verificación y límites

Casos automatizados en `tests/test_ui.py`, `tests/test_device_picker.py` y JavaScript;
regresión y comandos observados en
[PRUEBAS.md](PRUEBAS.md). No hay dependencias ni migraciones nuevas.
El navegador de la sesión no está disponible (selección fallida y lista vacía).
La estructura HTML se comprueba automáticamente; quedan por comprobar visualmente
los dropdowns, foco/teclado, contraste efectivo y anchos 1366/390 px con navegador real.
Para el selector: abrir/cerrar modal, cambiar filtros/página con equipos elegidos,
agregar todos, retirar/reagregar, verificar el orden y recorrerlo con teclado. Probar
escaneo sucesivo y permisos de cámara en un teléfono con HTTPS. Los dobles DOM de las
pruebas JavaScript no sustituyen esa validación visual ni una cámara física.
No se afirma validación visual, impresión física ni prueba de cámara.

Referencias: [Bootstrap dropdowns](https://getbootstrap.com/docs/5.3/components/dropdowns/),
[navbar responsive](https://getbootstrap.com/docs/5.3/components/navbar/),
[badges](https://getbootstrap.com/docs/5.3/components/badge/) y
[W3C: uso del color](https://www.w3.org/WAI/WCAG22/Understanding/use-of-color.html).
Selector: [Bootstrap modal](https://getbootstrap.com/docs/5.3/components/modal/),
[eventos HTMX](https://htmx.org/events/), [sincronización](https://htmx.org/attributes/hx-sync/)
y [filtros incluidos](https://htmx.org/attributes/hx-include/).
