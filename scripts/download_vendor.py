"""Fetch pinned frontend assets and verify upstream SHA-384 integrity hashes."""

import base64
import hashlib
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "static" / "vendor"
ASSETS = {
    "bootstrap.min.css": (
        "bootstrap@5.3.8/dist/css/bootstrap.min.css",
        "sRIl4kxILFvY47J16cr9ZwB07vP4J8+LH7qKQnuqkuIAvNWLzeN8tE5YBujZqJLB",
    ),
    "bootstrap.bundle.min.js": (
        "bootstrap@5.3.8/dist/js/bootstrap.bundle.min.js",
        "FKyoEForCGlyvwx9Hj09JcYn3nv7wiPVlz7YYwJrWVcXK/BmnVDxM+D2scQbITxI",
    ),
    "htmx.min.js": (
        "htmx.org@2.0.11/dist/htmx.min.js",
        "2OatzQy1H+Zd/IIrjr1TcuDGqLXeHhbooAyJY1KdQMKnr4LZ22k31GBLdYKHmVjg",
    ),
}


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    for filename, (package, expected) in ASSETS.items():
        with urllib.request.urlopen(
            f"https://cdn.jsdelivr.net/npm/{package}", timeout=30
        ) as response:
            data = response.read()
        actual = base64.b64encode(hashlib.sha384(data).digest()).decode()
        if actual != expected:
            raise ValueError(f"Integridad incorrecta: {filename}")
        (ROOT / filename).write_bytes(data)
        print(f"Verificado: {filename}")


if __name__ == "__main__":
    main()
