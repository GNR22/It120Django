"""
Phone-number validation and normalisation.

This module is deliberately independent of Django so it is easy to unit test.
It converts the many ways people type a number into E.164 format
(for example ``+639171234567``), which is what SMS providers like TextBee expect.
"""
import re


class InvalidPhoneNumber(ValueError):
    """Raised when text cannot be turned into a valid E.164 phone number."""


# Digits, spaces, dashes, dots, parentheses, and an optional leading "+".
_ALLOWED_CHARS = re.compile(r"^\+?[\d\s\-().]+$")

_PH_HELP = (
    "Philippine mobile numbers look like 09171234567 or +639171234567."
)


def normalize_phone(raw, default_country_code="63"):
    """Return ``raw`` as an E.164 string, or raise :class:`InvalidPhoneNumber`.

    Accepted examples (default country code 63 / Philippines):

    * ``09171234567``, ``0917 123 4567``, ``9171234567``
    * ``639171234567``, ``+63 917 123 4567``, ``0063 917 123 4567``
    * any other country in international format, e.g. ``+1 (415) 555-2671``
    """
    value = (raw or "").strip()
    if not value:
        raise InvalidPhoneNumber("Please enter the recipient's phone number.")

    if not _ALLOWED_CHARS.match(value):
        raise InvalidPhoneNumber(
            "Phone numbers may only contain digits, spaces, dashes, "
            "parentheses and a leading +."
        )

    has_plus = value.startswith("+")
    digits = re.sub(r"\D", "", value)

    if not has_plus and digits.startswith("00"):
        # 0063... style international prefix
        digits = digits[2:]
        has_plus = True

    if has_plus:
        national = digits
    elif digits.startswith("0"):
        # Local format with trunk prefix, e.g. 0917 123 4567
        national = default_country_code + digits[1:]
    elif digits.startswith(default_country_code) and len(digits) >= 11:
        # Already includes the country code, just without "+"
        national = digits
    else:
        # Local format without the trunk prefix, e.g. 917 123 4567
        national = default_country_code + digits

    if not national or national.startswith("0"):
        raise InvalidPhoneNumber(
            "That phone number does not start with a valid country code. "
            "Use the format +<country code><number>."
        )

    if national.startswith("63"):
        # Philippines: +63 9XX XXX XXXX  -> 12 digits, mobile numbers start with 9
        if len(national) != 12 or national[2] != "9":
            raise InvalidPhoneNumber(_PH_HELP)
    elif not 8 <= len(national) <= 15:
        raise InvalidPhoneNumber(
            "That phone number has the wrong length. Include the country "
            "code, for example +14155552671."
        )

    return "+" + national
