from datetime import date
from uuid import uuid4

from apps.maintenance.services import save_maintenance


def task_data(**overrides):
    return {
        "name": "Verificar conexiones",
        "scope": "DISPOSITIVO",
        "category_id": None,
        "required": True,
        **overrides,
    }


def maintenance_data(**overrides):
    return {
        "name": "Preventivo de prueba",
        "description": "Datos sintéticos",
        "is_recurring": False,
        "planned_date": date(2026, 12, 1),
        **overrides,
    }


def create_maintenance(test, **overrides):
    return save_maintenance(
        **{
            "actor": test.admin,
            "data": maintenance_data(),
            "device_ids": [test.device.pk],
            "tasks": [task_data()],
            "creation_key": uuid4(),
            **overrides,
        }
    )
