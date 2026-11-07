"""Read .env for development or an explicit --env-file, preserving existing variables."""

import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
environment_file = ROOT / ".env"
if sys.argv[1:2] == ["--env-file"]:
    if len(sys.argv) < 4:
        raise SystemExit("Use --env-file ARCHIVO seguido del comando Django.")
    environment_file = Path(sys.argv.pop(2))
    sys.argv.pop(1)
for line in environment_file.read_text(encoding="utf-8").splitlines():
    if line and not line.startswith("#") and "=" in line:
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)
sys.path.insert(0, str(ROOT))
runpy.run_path(str(ROOT / "manage.py"), run_name="__main__")
