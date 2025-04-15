import re
import datetime
from django.core.exceptions import ValidationError

def sanitize_card_number(value):
    """
    Remove spaces and dashes from the card number.
    """
    return re.sub(r'[\s-]', '', value)

def luhn_checksum_is_valid(card_number):
    """Return True if card_number passes the Luhn algorithm."""
    def digits_of(n):
        return [int(d) for d in str(n)]
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for d in even_digits:
        total += sum(digits_of(d * 2))
    return total % 10 == 0

def validate_card_number(value):
    """
    Sanitize and validate the card number.
    Raises a ValidationError if invalid.
    """
    sanitized = sanitize_card_number(value)
    if not sanitized.isdigit():
        raise ValidationError("Card number must contain only digits.")
    if not (12 <= len(sanitized) <= 19):
        raise ValidationError("Card number length must be between 12 and 19 digits.")
    if not luhn_checksum_is_valid(sanitized):
        raise ValidationError("Invalid card number (failed Luhn check).")
    return sanitized

def detect_card_type(card_number):
    """
    Very basic card type detection based on the card number prefix.
    Adjust and extend these rules as needed.
    """
    if card_number.startswith("4"):
        return "visa"
    elif card_number[:2] in ["51", "52", "53", "54", "55"]:
        return "master"
    # A common pattern for Verve cards in certain regions:
    elif card_number.startswith("5060") or card_number.startswith("650"):
        return "verve"
    return "unknown"

def mask_card_number(card_number):
    """
    Returns a masked version of the card number.
    For example, if the input is 16 digits, all but the last 4 digits are replaced with "*".
    """
    if len(card_number) <= 4:
        return card_number
    return "*" * (len(card_number) - 4) + card_number[-4:]
    
def validate_expiration_date(value):
    """
    Validate that the card expiration date is in the future.
    """
    if value < datetime.date.today():
        raise ValidationError("Card expiration date must be in the future.")
    return value
