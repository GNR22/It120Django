"""
Automated tests. TextBee is always mocked, so running these NEVER sends a real
SMS or uses your TextBee quota.

Run with:  python manage.py test
"""
from unittest.mock import patch

from django.conf import settings
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from textbee import TextbeeError

from .forms import SMSForm
from .models import SMSMessage
from .phone import InvalidPhoneNumber, normalize_phone

FAKE_TEXTBEE = {
    "TEXTBEE_API_KEY": "tb_test_secret_key_123",
    "SMS_DAILY_LIMIT": 50,
}
VALID_PHONE = "09171234567"
VALID_E164 = "+639171234567"


# --------------------------------------------------------------------------
# Phone-number normalisation (no database, no Django needed beyond the runner)
# --------------------------------------------------------------------------
class PhoneNormalizationTests(SimpleTestCase):
    def test_accepted_formats_become_e164(self):
        samples = [
            "09171234567",
            "0917 123 4567",
            "0917-123-4567",
            "9171234567",
            "639171234567",
            "+639171234567",
            "+63 917 123 4567",
            "0063 917 123 4567",
        ]
        for raw in samples:
            with self.subTest(raw=raw):
                self.assertEqual(normalize_phone(raw), VALID_E164)

    def test_international_numbers_from_other_countries(self):
        self.assertEqual(normalize_phone("+1 (415) 555-2671"), "+14155552671")

    def test_invalid_numbers_are_rejected(self):
        samples = ["", "   ", "abc", "12345", "0812345678", "+6391712345",
                   "+0123456789", "+1234567890123456", "0917@1234567"]
        for raw in samples:
            with self.subTest(raw=raw):
                with self.assertRaises(InvalidPhoneNumber):
                    normalize_phone(raw)


# --------------------------------------------------------------------------
# Form validation
# --------------------------------------------------------------------------
class SMSFormTests(SimpleTestCase):
    def test_valid_input(self):
        form = SMSForm({"phone_number": VALID_PHONE, "message": "Hello"})
        self.assertTrue(form.is_valid())
        self.assertEqual(form.cleaned_data["phone_number"], VALID_E164)

    def test_empty_phone_number(self):
        form = SMSForm({"phone_number": "", "message": "Hello"})
        self.assertFalse(form.is_valid())
        self.assertIn(
            "Please enter the recipient's phone number.",
            form.errors["phone_number"],
        )

    def test_empty_message(self):
        form = SMSForm({"phone_number": VALID_PHONE, "message": ""})
        self.assertFalse(form.is_valid())
        self.assertIn("Please type a message to send.", form.errors["message"])

    def test_whitespace_only_message(self):
        form = SMSForm({"phone_number": VALID_PHONE, "message": "    \n  "})
        self.assertFalse(form.is_valid())
        self.assertIn("message", form.errors)

    def test_invalid_phone_format(self):
        form = SMSForm({"phone_number": "12345", "message": "Hello"})
        self.assertFalse(form.is_valid())
        self.assertIn("phone_number", form.errors)

    def test_message_too_long(self):
        form = SMSForm({
            "phone_number": VALID_PHONE,
            "message": "x" * (settings.SMS_MAX_LENGTH + 1),
        })
        self.assertFalse(form.is_valid())
        self.assertIn("message", form.errors)


# --------------------------------------------------------------------------
# Send view (TextBee mocked)
# --------------------------------------------------------------------------
@override_settings(**FAKE_TEXTBEE)
class SendViewTests(TestCase):
    def setUp(self):
        self.url = reverse("sms_app:send")

    def _post(self, phone=VALID_PHONE, message="Hello from the tests", **kwargs):
        return self.client.post(
            self.url, {"phone_number": phone, "message": message}, **kwargs
        )

    def test_get_shows_the_form(self):
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Recipient phone number")
        self.assertContains(response, "Send SMS")

    def test_csrf_token_is_present_in_form(self):
        response = self.client.get(self.url)
        self.assertContains(response, "csrfmiddlewaretoken")

    @patch("sms_app.services.Textbee")
    def test_empty_phone_is_rejected_without_calling_textbee(self, client_cls):
        response = self._post(phone="")
        self.assertEqual(response.status_code, 200)
        self.assertIn("phone_number", response.context["form"].errors)
        client_cls.assert_not_called()
        self.assertEqual(SMSMessage.objects.count(), 0)

    @patch("sms_app.services.Textbee")
    def test_empty_message_is_rejected_without_calling_textbee(self, client_cls):
        response = self._post(message="")
        self.assertEqual(response.status_code, 200)
        self.assertIn("message", response.context["form"].errors)
        client_cls.assert_not_called()
        self.assertEqual(SMSMessage.objects.count(), 0)

    @patch("sms_app.services.Textbee")
    def test_invalid_phone_is_rejected_without_calling_textbee(self, client_cls):
        response = self._post(phone="not-a-number")
        self.assertEqual(response.status_code, 200)
        self.assertIn("phone_number", response.context["form"].errors)
        client_cls.assert_not_called()

    @patch("sms_app.services.Textbee")
    def test_successful_submission(self, client_cls):
        client_cls.return_value.send_sms.return_value = {
            "success": True,
            "smsBatchId": "batch_123",
            "recipientCount": 1,
        }
        response = self._post(follow=True)

        client_cls.assert_called_once_with(api_key=FAKE_TEXTBEE["TEXTBEE_API_KEY"])
        client_cls.return_value.send_sms.assert_called_once_with(
            recipients=[VALID_E164], message="Hello from the tests"
        )
        record = SMSMessage.objects.get()
        self.assertEqual(record.outcome, SMSMessage.Outcome.SUBMITTED)
        self.assertEqual(record.provider_sid, "batch_123")
        self.assertEqual(record.provider_status, "pending")
        # Must say "submitted", and must not claim delivery.
        self.assertContains(response, "Submitted to TextBee")
        self.assertContains(response, "not that the phone received it")
        self.assertEqual(record.delivery_label, "Submitted - delivery not yet confirmed")

    @patch("sms_app.services.Textbee")
    def test_missing_credentials_are_handled(self, client_cls):
        with override_settings(TEXTBEE_API_KEY=""):
            response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "not configured")
        client_cls.assert_not_called()
        self.assertEqual(SMSMessage.objects.get().outcome, SMSMessage.Outcome.FAILED)

    @patch("sms_app.services.Textbee")
    def test_incorrect_credentials_do_not_leak_secrets(self, client_cls):
        client_cls.return_value.send_sms.side_effect = TextbeeError(
            401, "Unauthorized"
        )
        response = self._post()
        self.assertContains(response, "rejected the API key")
        body = response.content.decode()
        self.assertNotIn(FAKE_TEXTBEE["TEXTBEE_API_KEY"], body)
        self.assertEqual(SMSMessage.objects.get().error_code, "401")

    @patch("sms_app.services.Textbee")
    def test_network_error_shows_friendly_message(self, client_cls):
        client_cls.return_value.send_sms.side_effect = OSError("boom")
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Could not reach TextBee")
        self.assertEqual(SMSMessage.objects.get().outcome, SMSMessage.Outcome.FAILED)

    @patch("sms_app.services.Textbee")
    def test_rate_limit_error_is_friendly(self, client_cls):
        client_cls.return_value.send_sms.side_effect = TextbeeError(
            429, "Too Many Requests"
        )
        response = self._post()
        self.assertContains(response, "rate-limiting")

    @patch("sms_app.services.Textbee")
    def test_unknown_provider_error_is_generic(self, client_cls):
        client_cls.return_value.send_sms.side_effect = TextbeeError(
            500, "Something internal"
        )
        response = self._post()
        self.assertContains(response, "status 500")
        self.assertNotContains(response, "Something internal")

    @patch("sms_app.services.Textbee")
    def test_unexpected_exception_is_contained(self, client_cls):
        client_cls.return_value.send_sms.side_effect = RuntimeError("kaboom")
        response = self._post()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "unexpected error")
        self.assertNotContains(response, "kaboom")

    @patch("sms_app.services.Textbee")
    def test_daily_limit_blocks_sending(self, client_cls):
        SMSMessage.objects.create(
            recipient=VALID_E164, body="earlier", outcome=SMSMessage.Outcome.SUBMITTED
        )
        with override_settings(SMS_DAILY_LIMIT=1):
            response = self._post()
        self.assertContains(response, "Daily limit reached")
        client_cls.assert_not_called()

    @patch("sms_app.services.Textbee")
    def test_form_input_is_kept_when_sending_fails(self, client_cls):
        client_cls.return_value.send_sms.side_effect = TimeoutError("slow")
        response = self._post(message="Please keep me")
        self.assertContains(response, "Please keep me")


# --------------------------------------------------------------------------
# History / status tracking
# --------------------------------------------------------------------------
@override_settings(**FAKE_TEXTBEE)
class HistoryViewTests(TestCase):
    def setUp(self):
        self.record = SMSMessage.objects.create(
            recipient=VALID_E164,
            body="Status check message",
            outcome=SMSMessage.Outcome.SUBMITTED,
            provider_sid="batch_777",
            provider_status="pending",
        )

    def test_history_lists_messages_and_masks_numbers(self):
        response = self.client.get(reverse("sms_app:history"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Status check message")
        self.assertContains(response, "+639******567")
        self.assertNotContains(response, VALID_E164)

    def test_history_empty_state(self):
        SMSMessage.objects.all().delete()
        response = self.client.get(reverse("sms_app:history"))
        self.assertContains(response, "No messages yet")

    @patch("sms_app.services.Textbee")
    def test_refresh_status_updates_to_delivered(self, client_cls):
        client_cls.return_value.get_messages.return_value = {
            "data": [{"status": "delivered"}],
            "meta": {"limit": 50},
        }
        response = self.client.post(
            reverse("sms_app:refresh_status", args=[self.record.pk]), follow=True
        )
        client_cls.return_value.get_messages.assert_called_once_with(
            sms_batch_id="batch_777"
        )
        self.record.refresh_from_db()
        self.assertEqual(self.record.provider_status, "delivered")
        self.assertIsNotNone(self.record.status_updated_at)
        self.assertContains(response, "Delivered (confirmed by TextBee)")

    @patch("sms_app.services.Textbee")
    def test_refresh_status_handles_empty_data(self, client_cls):
        client_cls.return_value.get_messages.return_value = {
            "data": [],
            "meta": {"limit": 50},
        }
        response = self.client.post(
            reverse("sms_app:refresh_status", args=[self.record.pk]), follow=True
        )
        self.record.refresh_from_db()
        self.assertEqual(self.record.provider_status, "unknown")
        self.assertContains(response, "Submitted - delivery not yet confirmed")

    @patch("sms_app.services.Textbee")
    def test_refresh_status_handles_network_error(self, client_cls):
        client_cls.return_value.get_messages.side_effect = OSError("down")
        response = self.client.post(
            reverse("sms_app:refresh_status", args=[self.record.pk]), follow=True
        )
        self.record.refresh_from_db()
        self.assertEqual(self.record.provider_status, "pending")  # unchanged
        self.assertContains(response, "Could not reach TextBee")

    def test_refresh_requires_post(self):
        response = self.client.get(
            reverse("sms_app:refresh_status", args=[self.record.pk])
        )
        self.assertEqual(response.status_code, 405)
