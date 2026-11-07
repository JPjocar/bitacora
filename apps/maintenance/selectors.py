from .models import MaintenanceRun, MaintenanceRunDevice


def has_pending_work(device_id):
    """Read-only integration: deactivating configuration does not close its execution."""
    return MaintenanceRunDevice.objects.filter(
        target__device_id=device_id,
        result="SIN_FINALIZAR",
        run__state__in=[
            MaintenanceRun.State.PENDING,
            MaintenanceRun.State.ASSIGNED,
            MaintenanceRun.State.RUNNING,
        ],
    ).exists()
