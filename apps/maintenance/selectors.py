from .models import MaintenanceRunDevice


def has_pending_work(device_id):
    """Read-only integration: deactivating configuration does not close its execution."""
    return MaintenanceRunDevice.objects.filter(
        target__device_id=device_id,
        result="SIN_FINALIZAR",
        run__state="PENDIENTE_ATENCION",
    ).exists()
