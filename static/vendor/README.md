# Dependencias frontend locales

- Bootstrap 5.3.8: `bootstrap.min.css`, `bootstrap.bundle.min.js`.
- HTMX 2.0.11: `htmx.min.js`.
- html5-qrcode 2.3.8: `html5-qrcode.min.js`, licencia Apache 2.0 adjunta.

Descargadas desde jsDelivr: Bootstrap/HTMX con hashes oficiales; html5-qrcode con
SHA-384 calculado del paquete 2.3.8 y fijado en el script para futuras descargas.
Los archivos se sirven desde Django static; no requieren acceso a CDN al navegar.
Para reproducir la descarga: `python scripts/download_vendor.py`.

Las URLs de origen y hashes están fijados en ese script. No se usan versiones `latest`.
Bootstrap: licencia MIT; HTMX: licencia Zero-Clause BSD. Avisos originales conservados.
