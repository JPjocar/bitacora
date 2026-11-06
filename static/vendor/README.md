# Dependencias frontend locales

- Bootstrap 5.3.8: `bootstrap.min.css`, `bootstrap.bundle.min.js`.
- HTMX 2.0.11: `htmx.min.js`.

Descargadas desde jsDelivr, con hashes SHA-384 verificados contra documentación oficial.
Los archivos se sirven desde Django static; no requieren acceso a CDN al navegar.
Para reproducir la descarga: `python scripts/download_vendor.py`.

Las URLs de origen y hashes están fijados en ese script. No se usan versiones `latest`.
Bootstrap: licencia MIT; HTMX: licencia Zero-Clause BSD. Avisos originales conservados.
