from apps.assets.services import save_category, save_device
from apps.locations.models import Location

from .helpers import setup_users


def setup_assets(cls):
    setup_users(cls)
    cls.category = save_category(
        actor=cls.admin, data={"name": "Categoría de prueba", "kind": "PC"}
    )
    cls.origin = Location.objects.create(
        name="Laboratorio de prueba", kind=Location.Kind.LABORATORY
    )
    cls.destination = Location.objects.create(
        name="Taller de prueba", kind=Location.Kind.MAINTENANCE
    )
    cls.other = Location.objects.create(name="Almacén de prueba", kind=Location.Kind.STORAGE)
    cls.device = save_device(
        actor=cls.admin,
        data={
            "name": "Equipo de prueba",
            "category_id": cls.category.pk,
            "location_id": cls.origin.pk,
        },
    )


def device_data(test, **overrides):
    return {
        "name": "Equipo nuevo",
        "category_id": test.category.pk,
        "location_id": test.origin.pk,
        **overrides,
    }
