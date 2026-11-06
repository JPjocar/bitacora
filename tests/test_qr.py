import base64
from io import BytesIO
from urllib.parse import urlencode
from uuid import uuid4

import zxingcpp
from django.contrib.auth.models import Permission
from django.core.exceptions import ImproperlyConfigured, PermissionDenied, ValidationError
from django.test import Client, SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from apps.assets.checks import check_public_https, check_public_url
from apps.assets.models import Device, DeviceEvent, Movement
from apps.assets.qr import (
    MAX_LABELS,
    SCAN_ERROR,
    device_qr_png,
    device_url,
    label_sheets,
    public_origin,
    resolve_scan,
)
from apps.assets.services import move_device, save_device

from .asset_helpers import device_data, setup_assets
from .helpers import PASSWORD, create_user

ORIGIN = "https://bitacora.example.edu"


@override_settings(BITACORA_PUBLIC_URL=ORIGIN)
class QRTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        setup_assets(cls)

    def detail_url(self):
        return reverse("assets:detail", args=[self.device.public_id])

    def qr_url(self):
        return reverse("assets:qr_png", args=[self.device.public_id])

    def test_png_decodes_to_only_canonical_identity(self):
        image = Image.open(BytesIO(device_qr_png(self.device)))
        self.assertEqual(image.format, "PNG")
        self.assertEqual(image.width, image.height)
        decoded = zxingcpp.read_barcode(image)
        self.assertIsNotNone(decoded)
        self.assertEqual(decoded.text, ORIGIN + self.detail_url())
        self.assertNotIn(self.device.code, decoded.text)
        self.assertNotIn(self.device.name, decoded.text)
        # White quiet zone: four 10 px modules on every edge.
        mono = image.convert("L")
        for box in (
            (0, 0, image.width, 40),
            (0, 0, 40, image.height),
            (image.width - 40, 0, image.width, image.height),
            (0, image.height - 40, image.width, image.height),
        ):
            self.assertEqual(mono.crop(box).getextrema(), (255, 255))

    def test_print_resolution_can_be_decoded(self):
        image = Image.open(BytesIO(device_qr_png(self.device)))
        # Approximate a 32 mm QR rendered at 300 dpi; independent decoder.
        printed = image.resize((378, 378), Image.Resampling.LANCZOS)
        self.assertEqual(zxingcpp.read_barcode(printed).text, device_url(self.device))

    def test_identity_survives_edit_and_movement(self):
        original = device_qr_png(self.device)
        edited = save_device(
            actor=self.admin,
            device_id=self.device.pk,
            expected_version=self.device.version,
            data={"name": "Nombre cambiado"},
        )
        move_device(
            actor=self.technician,
            device_id=edited.pk,
            destination_id=self.destination.pk,
            expected_version=edited.version,
            reason="Cambio de aula",
            effective_at=timezone.now(),
        )
        edited.refresh_from_db()
        self.assertEqual(device_qr_png(edited), original)

    def test_host_header_cannot_change_png_payload(self):
        self.client.force_login(self.admin)
        with override_settings(ALLOWED_HOSTS=["other.example.edu"]):
            response = self.client.get(self.qr_url(), HTTP_HOST="other.example.edu")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "image/png")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertEqual(
            zxingcpp.read_barcode(Image.open(BytesIO(response.content))).text,
            ORIGIN + self.detail_url(),
        )

    def test_anonymous_qr_and_scanner_require_login(self):
        for path in (self.qr_url(), reverse("assets:scanner"), reverse("assets:labels")):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("accounts:login")))

    def test_phone_url_returns_to_detail_after_login(self):
        response = self.client.get(self.detail_url())
        self.assertRedirects(
            response, reverse("accounts:login") + "?" + urlencode({"next": self.detail_url()})
        )
        response = self.client.post(
            reverse("accounts:login"),
            {"username": self.teacher.username, "password": PASSWORD, "next": self.detail_url()},
        )
        self.assertRedirects(response, self.detail_url())

    def test_all_three_roles_can_scan_and_read_visible_qr(self):
        for actor in (self.admin, self.technician, self.teacher):
            with self.subTest(actor=actor.username):
                self.client.force_login(actor)
                self.assertEqual(self.client.get(self.qr_url()).status_code, 200)
                self.assertEqual(self.client.get(reverse("assets:scanner")).status_code, 200)
                response = self.client.post(
                    reverse("assets:scanner"), {"query": device_url(self.device)}
                )
                self.assertRedirects(response, self.detail_url())

    def test_manual_code_is_trimmed_and_case_insensitive(self):
        self.assertEqual(
            resolve_scan(actor=self.teacher, value="  " + self.device.code.lower() + "  "),
            self.device,
        )

    def test_unknown_and_unauthorized_codes_are_indistinguishable(self):
        Device.objects.filter(pk=self.device.pk).update(is_active=False)
        for value in (self.device.code, device_url(self.device), "EQ-AAAAAAAA"):
            with self.subTest(value=value), self.assertRaisesMessage(ValidationError, SCAN_ERROR):
                resolve_scan(actor=self.teacher, value=value)

    def test_teacher_cannot_read_qr_for_retired_or_inactive_device(self):
        self.client.force_login(self.teacher)
        for data in ({"is_active": False}, {"is_active": True, "status": Device.Status.WITHDRAWN}):
            Device.objects.filter(pk=self.device.pk).update(**data)
            self.assertEqual(self.client.get(self.qr_url()).status_code, 404)

    def test_unknown_uuid_qr_is_404(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("assets:qr_png", args=[uuid4()]))
        self.assertEqual(response.status_code, 404)

    def test_external_or_malformed_qr_never_redirects(self):
        self.client.force_login(self.admin)
        path = self.detail_url()
        for value in (
            "https://evil.example" + path,
            "https://bitacora.example.edu.evil.example" + path,
            "https://bitacora.example.edu@evil.example" + path,
            "https://user:password@bitacora.example.edu" + path,
            "http://bitacora.example.edu" + path,
            "javascript:alert(1)",
            "//bitacora.example.edu" + path,
            path,
            ORIGIN + path + "?next=https://evil.example",
            ORIGIN + path + "#fragment",
            ORIGIN + path + "?",
            ORIGIN + path.replace("dispositivos", "%64ispositivos"),
            ORIGIN + "/cuentas/usuarios/",
            ORIGIN + path + "editar/",
            ORIGIN + path.replace("/", "\\"),
            ORIGIN + path.replace("dispositivos", "dispo\nsitivos"),
            "https://bitacora.example.edu:99999" + path,
            "https://bitacora.example.edu:0" + path,
            ORIGIN + "/dispositivos/" + str(uuid4()) + "/",
        ):
            with self.subTest(value=value):
                response = self.client.post(reverse("assets:scanner"), {"query": value})
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, SCAN_ERROR)
                self.assertNotIn("Location", response)

    def test_equivalent_default_port_is_accepted(self):
        self.assertEqual(
            resolve_scan(actor=self.admin, value=ORIGIN + ":443" + self.detail_url()), self.device
        )

    def test_empty_and_oversize_scan_show_form_errors(self):
        self.client.force_login(self.teacher)
        for value in ("", "a" * 2049):
            response = self.client.post(reverse("assets:scanner"), {"query": value})
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.context["form"].errors)

    def test_no_role_is_denied_all_qr_routes(self):
        actor = create_user("sin-rol")
        self.client.force_login(actor)
        for path in (reverse("assets:scanner"), reverse("assets:labels"), self.qr_url()):
            self.assertEqual(self.client.get(path).status_code, 403)

    def test_teacher_cannot_print_even_by_direct_request(self):
        self.client.force_login(self.teacher)
        for method in (self.client.get, self.client.post):
            self.assertEqual(
                method(reverse("assets:labels"), {"device": self.device.public_id}).status_code,
                403,
            )
        with self.assertRaises(PermissionDenied):
            label_sheets(actor=self.teacher, identifiers=[self.device.public_id])

    def test_admin_and_technician_can_print(self):
        for actor in (self.admin, self.technician):
            self.client.force_login(actor)
            response = self.client.get(reverse("assets:labels"), {"device": self.device.public_id})
            self.assertContains(response, self.device.code)
            self.assertContains(response, 'class="device-label"', count=1)
            self.assertIn("no-store", response["Cache-Control"])

    def test_print_selection_is_deduplicated(self):
        sheets = label_sheets(
            actor=self.admin, identifiers=[self.device.public_id, self.device.public_id]
        )
        self.assertEqual(len(sheets), 1)
        self.assertEqual(len(sheets[0]), 1)
        self.assertEqual(
            zxingcpp.read_barcode(Image.open(BytesIO(base64.b64decode(sheets[0][0]["png"])))).text,
            device_url(self.device),
        )

    def test_invalid_empty_missing_or_excess_selection_is_rejected(self):
        self.client.force_login(self.admin)
        for identifiers in (
            [],
            ["not-a-uuid"],
            [self.device.public_id, uuid4()],
            [self.device.public_id] * (MAX_LABELS + 1),
        ):
            with self.subTest(identifiers=str(identifiers)[:60]):
                response = self.client.post(reverse("assets:labels"), {"device": identifiers})
                self.assertEqual(response.status_code, 400)
                self.assertNotContains(response, 'class="device-label"', status_code=400)

    def test_print_permission_does_not_bypass_visibility(self):
        self.teacher.user_permissions.add(Permission.objects.get(codename="print_device_label"))
        Device.objects.filter(pk=self.device.pk).update(is_active=False)
        with self.assertRaises(ValidationError):
            label_sheets(actor=self.teacher, identifiers=[self.device.public_id])

    def test_label_sheets_have_at_most_fifteen_labels_and_no_blank_sheet(self):
        devices = [self.device]
        for index in range(15):
            devices.append(
                save_device(actor=self.admin, data=device_data(self, name=f"Equipo {index}"))
            )
        for count, sizes in ((15, [15]), (16, [15, 1])):
            sheets = label_sheets(
                actor=self.admin, identifiers=[device.public_id for device in devices[:count]]
            )
            self.assertEqual([len(sheet) for sheet in sheets], sizes)

    def test_scan_and_print_do_not_change_business_data(self):
        counts = Device.objects.count(), DeviceEvent.objects.count(), Movement.objects.count()
        before = Device.objects.values().get(pk=self.device.pk)
        label_sheets(actor=self.admin, identifiers=[self.device.public_id])
        resolve_scan(actor=self.admin, value=device_url(self.device))
        self.assertEqual(Device.objects.values().get(pk=self.device.pk), before)
        self.assertEqual(
            (Device.objects.count(), DeviceEvent.objects.count(), Movement.objects.count()), counts
        )

    def test_print_buttons_follow_permissions_in_full_and_htmx_list(self):
        for actor in (self.admin, self.teacher):
            self.client.force_login(actor)
            for headers in ({}, {"HTTP_HX_REQUEST": "true"}):
                response = self.client.get(reverse("assets:list"), **headers)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(b"Imprimir seleccionados" in response.content, actor == self.admin)
                if headers:
                    self.assertNotContains(response, "<!doctype")

    def test_post_forms_require_csrf(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.admin)
        for name, data in (
            ("scanner", {"query": self.device.code}),
            ("labels", {"device": self.device.public_id}),
        ):
            self.assertEqual(client.post(reverse(f"assets:{name}"), data).status_code, 403)
        client.get(reverse("assets:scanner"))
        response = client.post(
            reverse("assets:scanner"),
            {"query": self.device.code, "csrfmiddlewaretoken": client.cookies["csrftoken"].value},
        )
        self.assertEqual(response.status_code, 302)

    def test_png_and_labels_reject_unsupported_methods(self):
        self.client.force_login(self.admin)
        self.assertEqual(self.client.post(self.qr_url()).status_code, 405)
        self.assertEqual(self.client.delete(reverse("assets:labels")).status_code, 405)


class PublicOriginTests(SimpleTestCase):
    def test_bad_origins_fail_system_check(self):
        for value in (
            "",
            "bitacora.example.edu",
            "ftp://bitacora.example.edu",
            ORIGIN + "/app/",
            ORIGIN + "?a=1",
            ORIGIN + "#",
            ORIGIN + ":99999",
            "https://user:pass@bitacora.example.edu",
            ORIGIN + "/\n",
            "https://" + "a" * 190 + ".example.edu",
        ):
            with self.subTest(value=value), override_settings(BITACORA_PUBLIC_URL=value):
                with self.assertRaises(ImproperlyConfigured):
                    public_origin()
                self.assertEqual(check_public_url(None)[0].id, "assets.E001")

    @override_settings(BITACORA_PUBLIC_URL=ORIGIN + "/")
    def test_trailing_slash_is_normalized(self):
        self.assertEqual(public_origin(), ORIGIN)
        self.assertEqual(check_public_url(None), [])

    @override_settings(BITACORA_PUBLIC_URL="http://127.0.0.1:8000")
    def test_http_works_locally_but_fails_deployment_check(self):
        self.assertEqual(check_public_url(None), [])
        self.assertEqual(check_public_https(None)[0].id, "assets.E002")

    @override_settings(BITACORA_PUBLIC_URL=ORIGIN)
    def test_https_passes_deployment_check(self):
        self.assertEqual(check_public_https(None), [])
