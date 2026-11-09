import re
from uuid import uuid4

from django.db import connection
from django.test import Client, TestCase, override_settings
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from apps.assets.models import Device
from apps.assets.qr import device_url
from apps.maintenance.models import Maintenance, MaintenanceEvent

from .asset_helpers import setup_assets
from .maintenance_helpers import create_maintenance


@override_settings(BITACORA_PUBLIC_URL="https://bitacora.example.edu")
class DevicePickerTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_assets(cls)
        cls.extra = Device.objects.bulk_create(
            [
                Device(
                    name=f"Equipo {index:03}",
                    category=cls.category,
                    location=cls.origin,
                    created_by=cls.admin,
                )
                for index in range(99)
            ]
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def picker(self, **query):
        return self.client.get(reverse("maintenance:device_picker"), query, HTTP_HX_REQUEST="true")

    def payload(self, **kwargs):
        return {
            "name": "Preventivo con selector",
            "kind": "unique",
            "planned_date": timezone.localdate().isoformat(),
            "creation_key": uuid4(),
            "devices": [self.device.pk],
            "tasks-TOTAL_FORMS": "1",
            "tasks-INITIAL_FORMS": "0",
            "tasks-0-name": "Verificar conexiones",
            "tasks-0-scope": "DISPOSITIVO",
            "tasks-0-required": "on",
            "tasks-0-ORDER": "1",
            **kwargs,
        }

    def test_initial_form_does_not_query_or_render_the_inventory(self):
        with CaptureQueriesContext(connection) as queries:
            response = self.client.get(reverse("maintenance:create"))
        self.assertContains(response, 'id="device-grid"')
        self.assertContains(response, 'id="device-add"')
        self.assertNotContains(response, "data-device-card")
        self.assertNotContains(response, self.device.code)
        inventory_queries = [
            item["sql"] for item in queries if 'FROM "assets_device"' in item["sql"]
        ]
        self.assertEqual(inventory_queries, [])
        html = response.content.decode()
        self.assertGreater(html.index('id="device-picker-modal"'), html.index("</form>"))

    def test_search_is_paginated_twenty_at_a_time_for_one_hundred_devices(self):
        first, second = self.picker(), self.picker(page=2)
        self.assertEqual(first.context["page_obj"].paginator.count, 100)
        self.assertEqual(len(first.context["page_obj"]), 20)
        self.assertEqual(len(second.context["page_obj"]), 20)
        self.assertEqual(first.content.count(b"data-picker-device"), 20)
        first_ids = {item.pk for item in first.context["page_obj"]}
        second_ids = {item.pk for item in second.context["page_obj"]}
        self.assertFalse(first_ids & second_ids)
        self.assertEqual(self.picker(page="invalid").context["page_obj"].number, 1)

    def test_search_by_name_code_and_location(self):
        for query in (self.device.name, self.device.code.lower(), "  " + self.device.code + "  "):
            response = self.picker(q=query)
            self.assertEqual([item.pk for item in response.context["page_obj"]], [self.device.pk])
        self.assertEqual(self.picker(q=self.origin.name).context["page_obj"].paginator.count, 100)
        Device.objects.filter(pk=self.device.pk).update(location=self.destination)
        response = self.picker(location=self.destination.pk)
        self.assertEqual([item.pk for item in response.context["page_obj"]], [self.device.pk])
        self.assertContains(self.picker(q="Equipo inexistente"), "No hay equipos")

    def test_select_all_covers_every_filtered_page(self):
        response = self.picker(mode="all", q="Equipo")
        self.assertEqual(len(response.context["devices"]), 100)
        self.assertEqual(response.content.count(b"<template data-picker-card="), 100)
        self.assertContains(response, "data-picker-selection")
        filtered = self.picker(mode="all", q=self.device.code)
        self.assertEqual([item.pk for item in filtered.context["devices"]], [self.device.pk])

    def test_select_all_refuses_more_than_two_hundred_without_partial_selection(self):
        Device.objects.bulk_create(
            [
                Device(
                    name=f"Equipo adicional {index}",
                    category=self.category,
                    location=self.origin,
                    created_by=self.admin,
                )
                for index in range(101)
            ]
        )
        response = self.picker(mode="all")
        self.assertContains(response, "supera 200")
        self.assertNotContains(response, "data-picker-selection")
        self.assertNotContains(response, "data-picker-card=")

    def test_code_and_qr_url_return_one_card_for_automatic_selection(self):
        for value in (
            self.device.code.lower(),
            "  " + self.device.code + "  ",
            device_url(self.device),
        ):
            response = self.picker(mode="scan", query=value)
            self.assertEqual([item.pk for item in response.context["devices"]], [self.device.pk])
            self.assertContains(response, "data-picker-selection")
            self.assertNotIn("Location", response)

    def test_invalid_foreign_qr_missing_device_and_unbounded_inputs_are_rejected(self):
        values = [
            "",
            "invalid",
            "https://evil.example/",
            device_url(self.device) + "?next=/",
            f"https://bitacora.example.edu/dispositivos/{uuid4()}/",
            "x" * 2049,
        ]
        for value in values:
            with self.subTest(value=value[:60]):
                response = self.picker(mode="scan", query=value)
                self.assertNotContains(response, "data-picker-card=")
                self.assertTrue(response.context["picker_error"])
        for query in ({"location": "invalid"}, {"location": "9999999"}, {"q": "x" * 121}):
            response = self.picker(**query)
            self.assertTrue(response.context["picker_error"])
            self.assertEqual(response.context["page_obj"].paginator.count, 0)

    def test_inactive_or_retired_devices_excluded_but_existing_enrollment_retained_on_edit(self):
        maintenance = create_maintenance(self)
        Device.objects.filter(pk=self.device.pk).update(
            is_active=False, status=Device.Status.WITHDRAWN
        )
        self.assertEqual(self.picker(q=self.device.code).context["page_obj"].paginator.count, 0)
        self.assertTrue(self.picker(mode="scan", query=self.device.code).context["picker_error"])
        response = self.client.get(
            reverse("maintenance:device_picker_edit", args=[maintenance.pk]),
            {"mode": "scan", "query": self.device.code},
        )
        self.assertEqual([item.pk for item in response.context["devices"]], [self.device.pk])
        self.assertContains(response, "Inactivo")

    def test_permission_checks_on_create_and_edit_picker_and_post_is_unavailable(self):
        maintenance = create_maintenance(self)
        urls = [
            reverse("maintenance:device_picker"),
            reverse("maintenance:device_picker_edit", args=[maintenance.pk]),
        ]
        anonymous = Client()
        for url in urls:
            self.assertEqual(anonymous.get(url).status_code, 302)
            self.assertEqual(self.client.post(url).status_code, 405)
        for actor in (self.technician, self.teacher):
            self.client.force_login(actor)
            for url in urls:
                for query in ({}, {"mode": "all"}, {"mode": "scan", "query": self.device.code}):
                    self.assertEqual(self.client.get(url, query).status_code, 403)

    def test_picker_is_read_only_and_escapes_device_text(self):
        Device.objects.filter(pk=self.device.pk).update(name="<script>alert(1)</script>")
        before = MaintenanceEvent.objects.count()
        with CaptureQueriesContext(connection) as queries:
            response = self.picker(mode="scan", query=self.device.code)
        self.assertContains(response, "&lt;script&gt;")
        self.assertNotContains(response, "<script>alert(1)</script>")
        self.assertFalse(
            any(
                item["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE"))
                for item in queries
            )
        )
        self.assertEqual(MaintenanceEvent.objects.count(), before)
        self.assertFalse(Maintenance.objects.exists())

    def test_form_error_and_adding_task_preserve_selected_order(self):
        identifiers = [self.extra[2].pk, self.device.pk, self.extra[0].pk]
        for kwargs in ({"name": ""}, {"action": "add_task"}):
            response = self.client.post(
                reverse("maintenance:create"), self.payload(devices=identifiers, **kwargs)
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(
                [
                    int(value)
                    for value in re.findall(r'data-device-id="(\d+)"', response.content.decode())
                ],
                identifiers,
            )
            self.assertFalse(Maintenance.objects.exists())

    def test_without_javascript_add_and_remove_by_code_preserve_form_and_tasks(self):
        data = self.payload(action="add_device", device_query=self.extra[0].code)
        response = self.client.post(reverse("maintenance:create"), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'data-device-id="{self.extra[0].pk}"')
        self.assertContains(response, f'data-device-id="{self.device.pk}"')
        self.assertContains(response, 'value="Verificar conexiones"')
        self.assertFalse(Maintenance.objects.exists())
        data.update(devices=[self.extra[0].pk, self.device.pk], remove_device=str(self.device.pk))
        response = self.client.post(reverse("maintenance:create"), data)
        self.assertNotContains(response, f'data-device-id="{self.device.pk}"')
        self.assertContains(response, f'data-device-id="{self.extra[0].pk}"')
        self.assertFalse(Maintenance.objects.exists())

    def test_invalid_fallback_code_preserves_selection_without_saving(self):
        response = self.client.post(
            reverse("maintenance:create"), self.payload(action="add_device", device_query="invalid")
        )
        self.assertTrue(response.context["form"].errors["devices"])
        self.assertContains(response, f'data-device-id="{self.device.pk}"')
        self.assertFalse(Maintenance.objects.exists())

    def test_final_save_uses_existing_service_and_deduplicates_selection(self):
        response = self.client.post(
            reverse("maintenance:create"),
            self.payload(devices=[self.device.pk, self.extra[0].pk, self.device.pk]),
        )
        self.assertEqual(response.status_code, 302)
        maintenance = Maintenance.objects.get()
        self.assertEqual(maintenance.runs.count(), 1)
        self.assertEqual(maintenance.runs.get().participants.count(), 2)

    def test_no_longer_eligible_missing_or_over_limit_selection_cannot_save(self):
        Device.objects.filter(pk=self.device.pk).update(is_active=False)
        for identifiers in ([self.device.pk], [9999999], ["9" * 10000], [self.extra[0].pk] * 201):
            response = self.client.post(
                reverse("maintenance:create"), self.payload(devices=identifiers)
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn("devices", response.context["form"].errors)
            self.assertFalse(Maintenance.objects.exists())

    def test_edit_changes_future_enrollment_without_rewriting_current_run(self):
        maintenance = create_maintenance(self)
        run = maintenance.runs.get()
        before = list(run.participants.values())
        response = self.client.post(
            reverse("maintenance:edit", args=[maintenance.pk]),
            self.payload(
                devices=[self.extra[0].pk],
                version=maintenance.version,
                reason="Cambiar equipos para futuras ejecuciones",
                is_active="on",
            ),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(list(run.participants.values()), before)
        self.assertEqual(
            list(maintenance.targets.filter(is_active=True).values_list("device_id", flat=True)),
            [self.extra[0].pk],
        )
