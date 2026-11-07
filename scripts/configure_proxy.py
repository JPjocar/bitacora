"""Render an Nginx configuration; does not start a service or expose a network port."""

import argparse
import ipaddress
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def port(value):
    parsed = int(value)
    if not 1 <= parsed <= 65535:
        raise argparse.ArgumentTypeError("El puerto debe estar entre 1 y 65535.")
    return parsed


def quoted_path(value, *, directory=False):
    path = Path(value).resolve()
    if not (path.is_dir() if directory else path.is_file()):
        raise ValueError("Seleccione un archivo/directorio existente.")
    text = path.as_posix() + ("/" if directory else "")
    if any(char in text for char in ['"', "$", "\n", "\r", "{", "}"]):
        raise ValueError("La ruta contiene caracteres no admitidos en configuración Nginx.")
    return f'"{text}"'


def render(
    *, host, bind, http_port, https_port, upstream_port, certificate, key, static_root, mime_types
):
    if not re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9.-]{0,251}[A-Za-z0-9])?", host):
        raise ValueError("Use un nombre de host sin esquema, ruta ni puerto.")
    ipaddress.IPv4Address(bind)
    ports = [port(str(value)) for value in [http_port, https_port, upstream_port]]
    if len(set(ports)) != 3:
        raise ValueError("Los puertos HTTP, HTTPS y WSGI deben ser diferentes.")
    values = {
        "HOST": host,
        "BIND": bind,
        "HTTP_PORT": http_port,
        "HTTPS_PORT": https_port,
        "UPSTREAM_PORT": upstream_port,
        "TLS_SUFFIX": "" if https_port == 443 else f":{https_port}",
        "CERTIFICATE": quoted_path(certificate),
        "KEY": quoted_path(key),
        "STATIC_ROOT": quoted_path(static_root, directory=True),
        "MIME_TYPES": quoted_path(mime_types),
    }
    config = (ROOT / "deploy/nginx.conf.template").read_text(encoding="utf8")
    for name, value in values.items():
        config = config.replace(f"@@{name}@@", str(value))
    return config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--bind", default="127.0.0.1")
    parser.add_argument("--http-port", type=port, default=8088)
    parser.add_argument("--https-port", type=port, default=8443)
    parser.add_argument("--upstream-port", type=port, default=8081)
    for name in ["certificate", "key", "mime-types", "output"]:
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--static-root", type=Path, default=ROOT / "staticfiles")
    options = vars(parser.parse_args())
    output = options.pop("output")
    try:
        config = render(**options)
    except (ValueError, argparse.ArgumentTypeError) as error:
        parser.error(str(error))
    # Refuse accidental overwrites of a reviewed configuration.
    with output.open("x", encoding="utf8", newline="\n") as stream:
        stream.write(config)
    print(f"Configuración creada: {output}. Valide nginx -t antes de iniciarla.")


if __name__ == "__main__":
    main()
