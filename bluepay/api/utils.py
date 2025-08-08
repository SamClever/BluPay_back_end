import re
import datetime
from django.core.exceptions import ValidationError
import phonenumbers
import pycountry
from phonenumbers import COUNTRY_CODE_TO_REGION_CODE
import boto3
from botocore.exceptions import ClientError, BotoCoreError
import os
from django.conf import settings
import logging
import uuid
from django.utils.crypto import get_random_string
from decimal import Decimal
from bluepay.models import ClickPesaAPI

logger = logging.getLogger(__name__)


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



def validate_phone_number(phone_number, country_code='TZ'):
    """
    Validate phone number using phonenumbers library
    Returns: (is_valid: bool, formatted_number: str, error_message: str)
    """
    try:
        # Parse the phone number
        parsed_number = phonenumbers.parse(phone_number, country_code)
        
        # Check if it's valid
        if not phonenumbers.is_valid_number(parsed_number):
            return False, "", "Invalid phone number"
        
        # Format to international format
        formatted = phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
        
        return True, formatted, ""
    
    except phonenumbers.NumberParseException as e:
        return False, "", f"Phone number parsing error: {e}"
    except Exception as e:
        return False, "", f"Unexpected error: {e}"

def validate_tanzanian_phone(phone_number):
    """
    Validate Tanzanian phone number specifically
    Returns: (is_valid: bool, formatted_number: str, error_message: str)
    """
    try:
        # Remove any spaces or special characters
        phone = re.sub(r'[^\d+]', '', phone_number)
        
        # Check if it's a valid Tanzanian number
        if not re.match(r'^\+?255[67]\d{8}$', phone) and not re.match(r'^0[67]\d{8}$', phone):
            return False, "", "Invalid Tanzanian phone number. Please use format: +255XXXXXXXXX or 0XXXXXXXXX"
        
        # Normalize to international format
        if phone.startswith('0'):
            phone = '+255' + phone[1:]
        elif not phone.startswith('+'):
            phone = '+' + phone
            
        return True, phone, ""
    
    except Exception as e:
        return False, "", f"Phone validation error: {e}"

def generate_transaction_reference(prefix='BLU'):
    """
    Generate unique transaction reference
    """
    return f"{prefix}{get_random_string(10).upper()}"

def mask_sensitive_data(data, fields_to_mask=None):
    """
    Mask sensitive data in logs or responses
    """
    if fields_to_mask is None:
        fields_to_mask = ['pin', 'password', 'secret', 'token', 'phone']
    
    if isinstance(data, dict):
        masked_data = {}
        for key, value in data.items():
            if any(field in key.lower() for field in fields_to_mask):
                if isinstance(value, str) and len(value) > 4:
                    masked_data[key] = value[:2] + '*' * (len(value) - 4) + value[-2:]
                else:
                    masked_data[key] = '***'
            else:
                masked_data[key] = mask_sensitive_data(value, fields_to_mask)
        return masked_data
    elif isinstance(data, list):
        return [mask_sensitive_data(item, fields_to_mask) for item in data]
    else:
        return data

def calculate_transaction_fees(amount, transaction_type='DEPOSIT'):
    """
    Calculate transaction fees based on amount and type
    Returns: (fee_amount: Decimal, total_amount: Decimal)
    """
    amount = Decimal(str(amount))
    
    # Fee structure (can be moved to settings or database)
    fee_rates = {
        'DEPOSIT': {
            'percentage': Decimal('0.01'),  # 1%
            'minimum': Decimal('100'),      # 100 TZS
            'maximum': Decimal('5000'),     # 5000 TZS
        },
        'WITHDRAWAL': {
            'percentage': Decimal('0.015'), # 1.5%
            'minimum': Decimal('200'),      # 200 TZS
            'maximum': Decimal('10000'),    # 10000 TZS
        },
        'TRANSFER': {
            'percentage': Decimal('0.005'), # 0.5%
            'minimum': Decimal('50'),       # 50 TZS
            'maximum': Decimal('2000'),     # 2000 TZS
        }
    }
    
    if transaction_type not in fee_rates:
        return Decimal('0'), amount
    
    fee_config = fee_rates[transaction_type]
    
    # Calculate percentage-based fee
    fee_amount = amount * fee_config['percentage']
    
    # Apply minimum and maximum limits
    fee_amount = max(fee_amount, fee_config['minimum'])
    fee_amount = min(fee_amount, fee_config['maximum'])
    
    total_amount = amount + fee_amount
    
    return fee_amount, total_amount

def get_available_payment_methods(amount, currency='TZS'):
    """
    Get available payment methods from ClickPesa
    """
    
    clickpesa = ClickPesaAPI()
    temp_order_ref = generate_transaction_reference("TEMP")
    
    success, preview_data = clickpesa.preview_ussd_push(str(amount), currency, temp_order_ref)
    
    if success and 'activeMethods' in preview_data:
        available_methods = []
        unavailable_methods = []
        
        for method in preview_data['activeMethods']:
            if method.get('status') == 'AVAILABLE':
                available_methods.append({
                    'name': method.get('name'),
                    'fee': method.get('fee', 0),
                    'status': 'AVAILABLE'
                })
            else:
                unavailable_methods.append({
                    'name': method.get('name'),
                    'message': method.get('message', 'Unavailable'),
                    'status': 'UNAVAILABLE'
                })
        
        return {
            'success': True,
            'available_methods': available_methods,
            'unavailable_methods': unavailable_methods,
            'total_available': len(available_methods)
        }
    
    return {
        'success': False,
        'error': preview_data.get('error', 'Failed to get payment methods') if not success else 'No methods data',
        'available_methods': [],
        'unavailable_methods': [],
        'total_available': 0
    }

def get_country_phone_code_choices():
    """
    Returns a list of tuples [(dial_code, label), …] sorted by country name,
    where dial_code is e.g. "+1" and label is "United States (+1)".
    """
    seen = set()
    choices = []
    for dial, regions in COUNTRY_CODE_TO_REGION_CODE.items():
        for region in regions:
            if (region, dial) in seen:
                continue
            seen.add((region, dial))
            country = pycountry.countries.get(alpha_2=region)
            name = country.name if country else region
            choices.append((f"+{dial}", f"{name} (+{dial})"))
    return sorted(choices, key=lambda x: x[1])
