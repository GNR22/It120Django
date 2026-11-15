from django import forms
from django.conf import settings

from .phone import InvalidPhoneNumber, normalize_phone


class SMSForm(forms.Form):
    phone_number = forms.CharField(
        label="Recipient phone number",
        max_length=30,
        error_messages={
            "required": "Please enter the recipient's phone number.",
            "max_length": "That phone number is too long.",
        },
        widget=forms.TextInput(
            attrs={
                "placeholder": "e.g. 0917 123 4567 or +63 917 123 4567",
                "autocomplete": "off",
                "inputmode": "tel",
            }
        ),
    )
    message = forms.CharField(
        label="Message",
        error_messages={"required": "Please type a message to send."},
        widget=forms.Textarea(
            attrs={"rows": 6, "placeholder": "Type your message here..."}
        ),
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Lets the browser stop typing and lets the JS counter know the limit.
        self.fields["message"].widget.attrs["maxlength"] = settings.SMS_MAX_LENGTH

    def clean_phone_number(self):
        raw = self.cleaned_data["phone_number"]
        try:
            return normalize_phone(raw, settings.SMS_DEFAULT_COUNTRY_CODE)
        except InvalidPhoneNumber as exc:
            raise forms.ValidationError(str(exc))

    def clean_message(self):
        message = self.cleaned_data["message"]  # already whitespace-stripped
        limit = settings.SMS_MAX_LENGTH
        if len(message) > limit:
            raise forms.ValidationError(
                f"Your message is {len(message)} characters long. "
                f"The limit is {limit}."
            )
        return message
