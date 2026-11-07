from uuid import uuid4

from apps.incidents.services import report_incident


def report(test, **kwargs):
    return report_incident(
        **{
            "actor": test.teacher,
            "device_id": test.device.pk,
            "symptoms": "El equipo no reconoce la conexión de red.",
            "creation_key": uuid4(),
            **kwargs,
        }
    )


def act(test, service, incident, **kwargs):
    incident.refresh_from_db()
    return service(
        **{
            "actor": test.technician,
            "incident_id": incident.pk,
            "expected_version": incident.version,
            **kwargs,
        }
    )
