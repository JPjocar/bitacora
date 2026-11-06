"""Development only: read plain .env entries, preserving existing environment values."""

import os
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
    if line and not line.startswith("#") and "=" in line:
        key, value = line.split("=", 1)
        os.environ.setdefault(key, value)
sys.path.insert(0, str(ROOT))
runpy.run_path(str(ROOT / "manage.py"), run_name="__main__")
