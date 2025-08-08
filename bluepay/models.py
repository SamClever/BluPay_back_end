from django.db import models
import uuid
from django.core.exceptions import ValidationError
import re
from shortuuid.django_fields import ShortUUIDField
from userAccount.models import User
from Accounts.models import Account
from typing import Dict, Optional, Tuple
import requests
from datetime import datetime, timedelta
from django.conf import settings
import logging
from decimal import Decimal
logger = logging.getLogger(__name__)
# Create your models here.


# -----------------------------------------------------------------------------
# Choices / Constants
# -----------------------------------------------------------------------------

TRANSACTION_TYPE = (
    ("transfer", "Transfer"),
    ("recieved", "Recieved"),
    ("withdraw", "withdraw"),
    ("refund", "Refund"),
    ("request", "Payment Request"),
    ("none", "None")
)

TRANSACTION_STATUS = (
    ("failed", "failed"),
    ("completed", "completed"),
    ("pending", "pending"),
    ("processing", "processing"),
    ("request_sent", "request_sent"),
    ("request_settled", "request settled"),
    ("request_processing", "request processing"),

)



CARD_TYPE = (
    ("visa", "Visa"),
    ("mastercard", "MasterCard"),
    ("american_express", "American Express"),
    ("discover", "Discover"),
    ("diners_club", "Diners Club International"),
    ("jcb", "JCB"),
    ("unionpay", "UnionPay"),
    ("maestro", "Maestro"),
    ("ru_pay", "RuPay"),
    ("hipercard", "Hipercard"),
    ("elo", "Elo"),
    ("mir", "MIR"),
)


# -----------------------------------------------------------------------------
# Helper Function: Luhn Check
# -----------------------------------------------------------------------------

class ClickPesaAPI:
    """ClickPesa API integration class"""
    
    def __init__(self):
        self.base_url = getattr(settings, 'CLICKPESA_BASE_URL', 'https://api.clickpesa.com/third-parties')
        self.client_id = getattr(settings, 'CLICKPESA_CLIENT_ID', '')
        self.api_key = getattr(settings, 'CLICKPESA_API_KEY', '')
        self.access_token = None
        self.token_expires_at = None

    def _get_headers(self) -> Dict[str, str]:
        """Get headers with authorization token"""
        if not self.access_token or self._is_token_expired():
            self._generate_token()
        
        return {
            'Authorization': self.access_token,  # Token already includes Bearer prefix
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

    def _is_token_expired(self) -> bool:
        """Check if current token is expired"""
        if not self.token_expires_at:
            return True
        return datetime.now() >= self.token_expires_at

    def _generate_token(self) -> bool:
        """Generate JWT authorization token"""
        try:
            url = f"{self.base_url}/generate-token"
            headers = {
                'client-id': self.client_id,
                'api-key': self.api_key,
                'Content-Type': 'application/json'
            }
            
            response = requests.post(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            token_data = response.json()
            
            if token_data.get('success'):
                self.access_token = token_data.get('token')  # Already includes Bearer prefix
                # JWT tokens are valid for 1 hour, refresh 5 minutes early
                self.token_expires_at = datetime.now() + timedelta(minutes=55)
                
                logger.info("ClickPesa token generated successfully")
                return True
            else:
                logger.error(f"Failed to generate ClickPesa token: {token_data}")
                return False
            
        except requests.RequestException as e:
            logger.error(f"Failed to generate ClickPesa token: {e}")
            return False

    def preview_ussd_push(self, amount: str, currency: str, order_reference: str) -> Tuple[bool, Optional[Dict]]:
        """Preview USSD push request"""
        try:
            url = f"{self.base_url}/payments/preview-ussd-push-request"
            headers = self._get_headers()
            
            payload = {
                "amount": str(amount),
                "currency": currency,
                "orderReference": order_reference
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"USSD push preview successful for {order_reference}")
                return True, data
            else:
                logger.error(f"USSD push preview failed: {response.status_code} - {response.text}")
                return False, {"error": f"Preview failed: {response.status_code}", "details": response.text}
            
        except requests.RequestException as e:
            logger.error(f"Network error in USSD push preview: {e}")
            return False, {"error": f"Network error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in USSD push preview: {e}")
            return False, {"error": f"Unexpected error: {str(e)}"}

    def initiate_ussd_push(self, amount: str, currency: str, order_reference: str, phone_number: str) -> Tuple[bool, Optional[Dict]]:
        """Initiate USSD push request"""
        try:
            url = f"{self.base_url}/payments/initiate-ussd-push-request"
            headers = self._get_headers()
            
            # Format phone number (remove + if present, ensure country code)
            formatted_phone = phone_number.replace('+', '').replace(' ', '')
            if formatted_phone.startswith('0'):
                formatted_phone = '255' + formatted_phone[1:]  # Convert to international format for Tanzania
            
            payload = {
                "amount": str(amount),
                "currency": currency,
                "orderReference": order_reference,
                "phoneNumber": formatted_phone
            }
            
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"USSD push initiated successfully for {order_reference}")
                return True, data
            else:
                logger.error(f"USSD push initiation failed: {response.status_code} - {response.text}")
                return False, {"error": f"Push failed: {response.status_code}", "details": response.text}
            
        except requests.RequestException as e:
            logger.error(f"Network error in USSD push initiation: {e}")
            return False, {"error": f"Network error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in USSD push initiation: {e}")
            return False, {"error": f"Unexpected error: {str(e)}"}

    def query_payment_status(self, order_reference: str) -> Tuple[bool, Optional[Dict]]:
        """Query payment status by order reference"""
        try:
            url = f"{self.base_url}/payments/{order_reference}"
            headers = self._get_headers()
            
            response = requests.get(url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Payment status queried successfully for {order_reference}")
                return True, data
            elif response.status_code == 404:
                logger.warning(f"Payment not found for order reference: {order_reference}")
                return False, {"error": "Payment not found"}
            elif response.status_code == 401:
                logger.error(f"Unauthorized access for order reference: {order_reference}")
                return False, {"error": "Unauthorized"}
            else:
                logger.error(f"Failed to query payment status: {response.status_code} - {response.text}")
                return False, {"error": f"API error: {response.status_code}"}
                
        except requests.RequestException as e:
            logger.error(f"Network error querying payment status: {e}")
            return False, {"error": f"Network error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error querying payment status: {e}")
            return False, {"error": f"Unexpected error: {str(e)}"}
        

    
    def preview_mobile_money_payout(self, amount: str, phone_number: str, currency: str, order_reference: str) -> Tuple[bool, Optional[Dict]]:
        """Preview mobile money payout"""
        try:
            url = f"{self.base_url}/payouts/preview-mobile-money-payout"
            headers = self._get_headers()
        
            # Format phone number (remove + if present, ensure country code)
            formatted_phone = phone_number.replace('+', '').replace(' ', '')
            if formatted_phone.startswith('0'):
                formatted_phone = '255' + formatted_phone[1:]  # Convert to international format for Tanzania
        
            payload = {
                "amount": float(amount),
                "phoneNumber": formatted_phone,
                "currency": currency,
                "orderReference": order_reference
            }
        
            response = requests.post(url, json=payload, headers=headers, timeout=30)
        
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Payout preview successful for {order_reference}")
                return True, data
            else:
                logger.error(f"Payout preview failed: {response.status_code} - {response.text}")
                return False, {"error": f"Preview failed: {response.status_code}", "details": response.text}
        
        except requests.RequestException as e:
            logger.error(f"Network error in payout preview: {e}")
            return False, {"error": f"Network error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error in payout preview: {e}")
            return False, {"error": f"Unexpected error: {str(e)}"}

    def create_mobile_money_payout(self, amount: str, phone_number: str, currency: str, order_reference: str) -> Tuple[bool, Optional[Dict]]:
        """Create mobile money payout"""
        try:
            url = f"{self.base_url}/payouts/create-mobile-money-payout"
            headers = self._get_headers()
        
            # Format phone number (remove + if present, ensure country code)
            formatted_phone = phone_number.replace('+', '').replace(' ', '')
            if formatted_phone.startswith('0'):
                formatted_phone = '255' + formatted_phone[1:]  # Convert to international format for Tanzania
        
            payload = {
                "amount": float(amount),
                "phoneNumber": formatted_phone,
                "currency": currency,
                "orderReference": order_reference
            }
        
            response = requests.post(url, json=payload, headers=headers, timeout=30)
        
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Payout created successfully for {order_reference}")
                return True, data
            else:
                logger.error(f"Payout creation failed: {response.status_code} - {response.text}")
                return False, {"error": f"Creation failed: {response.status_code}", "details": response.text}
        
        except requests.RequestException as e:
            logger.error(f"Network error in payout creation: {e}")
            return False, {"error": f"Network error: {str(e)}"}
        except Exception as e:
                logger.error(f"Unexpected error in payout creation: {e}")
                return False, {"error": f"Unexpected error: {str(e)}"}

    def query_payout_status(self, order_reference: str) -> Tuple[bool, Optional[Dict]]:
        """Query payout status by order reference"""
        try:
            url = f"{self.base_url}/payouts/{order_reference}"
            headers = self._get_headers()
        
            response = requests.get(url, headers=headers, timeout=30)
        
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Payout status queried successfully for {order_reference}")
                return True, data
            elif response.status_code == 404:
                logger.warning(f"Payout not found for order reference: {order_reference}")
                return False, {"error": "Payout not found"}
            elif response.status_code == 401:
                logger.error(f"Unauthorized access for payout order reference: {order_reference}")
                return False, {"error": "Unauthorized"}
            else:
                logger.error(f"Failed to query payout status: {response.status_code} - {response.text}")
                return False, {"error": f"API error: {response.status_code}"}
            
        except requests.RequestException as e:
            logger.error(f"Network error querying payout status: {e}")
            return False, {"error": f"Network error: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected error querying payout status: {e}")
            return False, {"error": f"Unexpected error: {str(e)}"}







def luhn_checksum_is_valid(card_number: str) -> bool:
    """
    Returns True if the card_number passes the Luhn check.
    """
    def digits_of(n):
        return [int(d) for d in n]
    digits = digits_of(card_number)
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for d in even_digits:
        total += sum(digits_of(str(d * 2)))
    return total % 10 == 0


NOTIFICATION_TYPE = (
    ("None", "None"),
    ("Transfer", "Transfer"),
    ("Credit Alert", "Credit Alert"),
    ("Debit Alert", "Debit Alert"),
    ("Sent Payment Request", "Sent Payment Request"),
    ("Recieved Payment Request", "Recieved Payment Request"),
    ("Funded Credit Card", "Funded Credit Card"),
    ("Withdrew Credit Card Funds", "Withdrew Credit Card Funds"),
    ("Deleted Credit Card", "Deleted Credit Card"),
    ("Added Credit Card", "Added Credit Card"),
    ("Updated Credit Card", "Updated Credit Card"),

)


# Payment Transaction choices (if needed separately)
PAYMENT_TRANSACTION_TYPE_CHOICES = (
    ('purchase', 'Purchase'),
    ('refund', 'Refund'),
    ('transfer', 'Transfer'),
)

PAYMENT_TRANSACTION_STATUS_CHOICES = (
    ('pending', 'Pending'),
    ('completed', 'Completed'),
    ('failed', 'Failed'),
)




PAYMENT_STATUS_CHOICES = [
    ('SUCCESS', 'Success'),
    ('SETTLED', 'Settled'),
    ('PROCESSING', 'Processing'),
    ('PENDING', 'Pending'),
    ('FAILED', 'Failed'),
]

PAYMENT_METHOD_CHOICES = [
    ('MOBILE_MONEY', 'Mobile Money'),
    ('CARD', 'Card'),
    ('BANK_TRANSFER', 'Bank Transfer'),
    ('USSD', 'USSD'),
]

TRANSACTION_TYPE_CHOICES = [
    ('DEPOSIT', 'Deposit'),
    ('WITHDRAWAL', 'Withdrawal'),
    ('TRANSFER', 'Transfer'),
    ('PAYMENT', 'Payment'),
]







class MobileMoneyProvider(models.Model):
    """Mobile money providers (e.g., M-Pesa, Airtel Money, etc.)"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    country = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.name} ({self.country})"

class Payment(models.Model):
    """Payment transactions with ClickPesa integration"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # ClickPesa fields
    payment_reference = models.CharField(max_length=100, unique=True)
    order_reference = models.CharField(max_length=100, unique=True)
    clickpesa_transaction_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Internal fields
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='payments')
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES)
    mobile_provider = models.ForeignKey(MobileMoneyProvider, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Amount and currency
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='TZS')
    collected_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    collected_currency = models.CharField(max_length=10, blank=True, null=True)
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    message = models.TextField(blank=True, null=True)
    
    # Customer information
    customer_name = models.CharField(max_length=200)
    customer_phone = models.CharField(max_length=20)
    customer_email = models.EmailField(blank=True, null=True)
    
    # Metadata
    client_id = models.CharField(max_length=100, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Topup functionality fields
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    ussd_push_initiated = models.BooleanField(default=False)
    preview_data = models.JSONField(default=dict, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    clickpesa_created_at = models.DateTimeField(null=True, blank=True)
    clickpesa_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_reference']),
            models.Index(fields=['payment_reference']),
            models.Index(fields=['status']),
            models.Index(fields=['account', 'status']),
        ]

    def __str__(self):
        return f"Payment {self.order_reference} - {self.status}"

    @property
    def is_successful(self):
        return self.status in ['SUCCESS', 'SETTLED']

    @property
    def is_pending(self):
        return self.status in ['PENDING', 'PROCESSING']

    @property
    def is_failed(self):
        return self.status == 'FAILED'

    def initiate_clickpesa_payment(self):
        """Initiate payment with ClickPesa"""
        clickpesa = ClickPesaAPI()
        
        # Preview first
        preview_success, preview_data = clickpesa.preview_ussd_push(
            str(self.amount), self.currency, self.order_reference
        )
        
        if not preview_success:
            return False, preview_data
        
        self.preview_data = preview_data
        
        # Check if any payment methods are available
        available_methods = [
            method for method in preview_data.get('activeMethods', [])
            if method.get('status') == 'AVAILABLE'
        ]
        
        if not available_methods:
            return False, {"error": "No payment methods available"}
        
        # Initiate USSD push
        push_success, push_data = clickpesa.initiate_ussd_push(
            str(self.amount), self.currency, self.order_reference, self.phone_number
        )
        
        if push_success:
            self.clickpesa_transaction_id = push_data.get('id')
            self.status = push_data.get('status', 'PROCESSING')
            self.client_id = push_data.get('clientId')
            self.ussd_push_initiated = True
            
            if 'channel' in push_data:
                self.metadata['channel'] = push_data['channel']
            if 'collectedAmount' in push_data:
                self.collected_amount = push_data['collectedAmount']
            if 'collectedCurrency' in push_data:
                self.collected_currency = push_data['collectedCurrency']
            
            self.save()
        
        return push_success, push_data

    def query_clickpesa_status(self):
        """Query payment status from ClickPesa"""
        clickpesa = ClickPesaAPI()
        success, api_data = clickpesa.query_payment_status(self.order_reference)
        
        if success:
            old_status = self.status
            
            # Update payment fields from API response
            if 'status' in api_data:
                self.status = api_data['status']
            if 'collectedAmount' in api_data:
                self.collected_amount = api_data['collectedAmount']
            if 'collectedCurrency' in api_data:
                self.collected_currency = api_data['collectedCurrency']
            if 'message' in api_data:
                self.message = api_data['message']
            
            # Update customer info if provided
            if 'customer' in api_data:
                customer = api_data['customer']
                if 'customerName' in customer:
                    self.customer_name = customer['customerName']
                if 'customerPhoneNumber' in customer:
                    self.customer_phone = customer['customerPhoneNumber']
                if 'customerEmail' in customer:
                    self.customer_email = customer['customerEmail']
            
            if old_status != self.status:
                self.save()
                
                # Create status history
                PaymentStatusHistory.objects.create(
                    payment=self,
                    previous_status=old_status,
                    new_status=self.status,
                    message="Status updated from API query"
                )
        
        return success, api_data

class PaymentStatusHistory(models.Model):
    """Track payment status changes"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='status_history')
    previous_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, null=True, blank=True)
    new_status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES)
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.payment.order_reference}: {self.previous_status} -> {self.new_status}"

class PaymentWebhook(models.Model):
    """Store webhook notifications from ClickPesa"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payment = models.ForeignKey(Payment, on_delete=models.CASCADE, related_name='webhooks', null=True, blank=True)
    order_reference = models.CharField(max_length=100)
    webhook_data = models.JSONField()
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Webhook for {self.order_reference} - {'Processed' if self.processed else 'Pending'}"









PAYOUT_STATUS_CHOICES = [
    ('AUTHORIZED', 'Authorized'),
    ('SUCCESS', 'Success'),
    ('PROCESSING', 'Processing'),
    ('PENDING', 'Pending'),
    ('FAILED', 'Failed'),
    ('REFUNDED', 'Refunded'),
    ('REVERSED', 'Reversed'),
]

PAYOUT_CHANNEL_CHOICES = [
    ('MOBILE_MONEY', 'Mobile Money'),
    ('BANK_TRANSFER', 'Bank Transfer'),
]

class Payout(models.Model):
    """Payout transactions with ClickPesa integration"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # ClickPesa fields
    payout_reference = models.CharField(max_length=100, unique=True)
    order_reference = models.CharField(max_length=100, unique=True)
    clickpesa_payout_id = models.CharField(max_length=100, blank=True, null=True)
    
    # Internal fields
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name='payouts')
    payout_type = models.CharField(max_length=20, default='WITHDRAWAL')
    channel = models.CharField(max_length=20, choices=PAYOUT_CHANNEL_CHOICES, default='MOBILE_MONEY')
    channel_provider = models.CharField(max_length=100, blank=True, null=True)
    
    # Amount and currency
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=10, default='TZS')
    fee = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2)  # amount + fee
    
    # Status and tracking
    status = models.CharField(max_length=20, choices=PAYOUT_STATUS_CHOICES, default='PENDING')
    message = models.TextField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    
    # Beneficiary information
    beneficiary_name = models.CharField(max_length=200)
    beneficiary_phone = models.CharField(max_length=20)
    beneficiary_email = models.EmailField(blank=True, null=True)
    
    # Metadata
    client_id = models.CharField(max_length=100, blank=True, null=True)
    metadata = models.JSONField(default=dict, blank=True)
    
    # Preview data
    preview_data = models.JSONField(default=dict, blank=True)
    payout_fee_bearer = models.CharField(max_length=20, default='customer')  # merchant, customer, both
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    clickpesa_created_at = models.DateTimeField(null=True, blank=True)
    clickpesa_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['order_reference']),
            models.Index(fields=['payout_reference']),
            models.Index(fields=['status']),
            models.Index(fields=['account', 'status']),
        ]

    def __str__(self):
        return f"Payout {self.order_reference} - {self.status}"

    @property
    def is_successful(self):
        return self.status == 'SUCCESS'

    @property
    def is_pending(self):
        return self.status in ['PENDING', 'PROCESSING', 'AUTHORIZED']

    @property
    def is_failed(self):
        return self.status in ['FAILED', 'REFUNDED', 'REVERSED']

    def preview_clickpesa_payout(self):
        """Preview payout with ClickPesa"""
        clickpesa = ClickPesaAPI()
        
        success, preview_data = clickpesa.preview_mobile_money_payout(
            str(self.amount), self.beneficiary_phone, self.currency, self.order_reference
        )
        
        if success:
            self.preview_data = preview_data
            self.fee = Decimal(str(preview_data.get('fee', 0)))
            self.total_amount = self.amount + self.fee
            self.channel_provider = preview_data.get('channelProvider', '')
            self.payout_fee_bearer = preview_data.get('payoutFeeBearer', 'customer')
            self.save()
        
        return success, preview_data

    def initiate_clickpesa_payout(self):
        """Initiate payout with ClickPesa"""
        clickpesa = ClickPesaAPI()
        
        # Preview first to get fees
        preview_success, preview_data = self.preview_clickpesa_payout()
        if not preview_success:
            return False, preview_data
        
        # Check account balance
        total_cost = self.amount + self.fee
        if self.account.account_balance < total_cost:
            return False, {"error": "Insufficient balance"}
        
        # Initiate payout
        success, payout_data = clickpesa.create_mobile_money_payout(
            str(self.amount), self.beneficiary_phone, self.currency, self.order_reference
        )
        
        if success:
            self.clickpesa_payout_id = payout_data.get('id')
            self.status = payout_data.get('status', 'PENDING')
            self.client_id = payout_data.get('clientId')
            self.channel_provider = payout_data.get('channelProvider', '')
            
            if 'createdAt' in payout_data:
                try:
                    self.clickpesa_created_at = datetime.fromisoformat(
                        payout_data['createdAt'].replace('Z', '+00:00')
                    )
                except:
                    pass
            
            # Deduct from account balance
            self.account.account_balance -= total_cost
            self.account.save()
            
            self.save()
        
        return success, payout_data

    def query_clickpesa_status(self):
        """Query payout status from ClickPesa"""
        clickpesa = ClickPesaAPI()
        success, api_data = clickpesa.query_payout_status(self.order_reference)
        
        if success:
            old_status = self.status
            
            # Update payout fields from API response
            if 'status' in api_data:
                self.status = api_data['status']
            if 'fee' in api_data:
                self.fee = Decimal(str(api_data['fee']))
            if 'notes' in api_data:
                self.notes = api_data['notes']
            if 'channelProvider' in api_data:
                self.channel_provider = api_data['channelProvider']
            
            # Update beneficiary info if provided
            if 'beneficiary' in api_data:
                beneficiary = api_data['beneficiary']
                if 'name' in beneficiary:
                    self.beneficiary_name = beneficiary['name']
                if 'phoneNumber' in beneficiary:
                    self.beneficiary_phone = beneficiary['phoneNumber']
            
            if old_status != self.status:
                self.save()
                
                # Create status history
                PayoutStatusHistory.objects.create(
                    payout=self,
                    previous_status=old_status,
                    new_status=self.status,
                    message="Status updated from API query"
                )
        
        return success, api_data

class PayoutStatusHistory(models.Model):
    """Track payout status changes"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payout = models.ForeignKey(Payout, on_delete=models.CASCADE, related_name='status_history')
    previous_status = models.CharField(max_length=20, choices=PAYOUT_STATUS_CHOICES, null=True, blank=True)
    new_status = models.CharField(max_length=20, choices=PAYOUT_STATUS_CHOICES)
    message = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.payout.order_reference}: {self.previous_status} -> {self.new_status}"

class PayoutWebhook(models.Model):
    """Store webhook notifications from ClickPesa for payouts"""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    payout = models.ForeignKey(Payout, on_delete=models.CASCADE, related_name='webhooks', null=True, blank=True)
    order_reference = models.CharField(max_length=100)
    webhook_data = models.JSONField()
    processed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Payout Webhook for {self.order_reference} - {'Processed' if self.processed else 'Pending'}"


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------

class Transaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_id = ShortUUIDField(unique=True, length=15, max_length=20, prefix="TRN")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="user")
    amount = models.DecimalField(max_digits=12, decimal_places=2,default=0.00)
    description = models.CharField(max_length=1000, null=True, blank=True)
    reference = models.CharField(max_length=50, unique=True, null=True, blank=True)

    reciver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="reciver")
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="sender")

    reciver_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, related_name="reciver_account")
    sender_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, related_name="sender_account")

    status = models.CharField(choices=TRANSACTION_STATUS ,max_length=100, default="pending")
    transaction_type = models.CharField(choices=TRANSACTION_TYPE ,max_length=100, default="none")

    date = models.DateTimeField(auto_now_add=True)
    update = models.DateTimeField(auto_now_add=False, null=True, blank=True)




    # Link to new Payment model
    payment = models.OneToOneField(Payment, on_delete=models.CASCADE, null=True, blank=True)

    


    def __str__(self):
        try:
            return f"{self.user}"
        except:
            return f"Transaction"
        



class VirtualCard(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    card_id = ShortUUIDField(unique=True, length=10, prefix="VCRD")
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="virtual_cards")
    card_token = models.CharField(max_length=255)
    card_name = models.CharField(max_length=255, blank=True)
    masked_number = models.CharField(max_length=20)
    expiration_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)

    default_card = models.BooleanField(default=False)

    card_type = models.CharField(max_length=20, choices=CARD_TYPE, blank=True, null=True)


    def clean(self):
        """
        Sanitizes and validates the card data:
          - Strips spaces and hyphens.
          - Ensures the card number is numeric.
          - Attempts to deduce the card type if not provided.
          - Validates the card number based on expected lengths, prefix patterns, and Luhn check.
        """
        # Sanitize the card number: remove spaces and hyphens.
        card_number = self.masked_number.replace(" ", "").replace("-", "")
        
        if not card_number.isdigit():
            raise ValidationError("Card number must contain only digits (spaces and dashes are allowed).")
        
        # Define the expected patterns for each card type.
        valid_patterns = {
            "visa": {"prefixes": ("4",), "lengths": (13, 16, 19)},
            "mastercard": {"prefixes": tuple(str(i) for i in range(51, 56)), "lengths": (16,)},
            "american_express": {"prefixes": ("34", "37"), "lengths": (15,)},
            "discover": {"prefixes": ("6011", "65") + tuple(str(i) for i in range(644, 650)), "lengths": (16,)},
            "diners_club": {"prefixes": ("300", "301", "302", "303", "304", "305", "36", "38"), "lengths": (14,)},
            "jcb": {"prefixes": ("35",), "lengths": (16,)},
            "unionpay": {"prefixes": ("62",), "lengths": (16, 17, 18, 19)},
            "maestro": {"prefixes": ("50", "56", "57", "58", "6304", "67"), "lengths": tuple(range(12, 20))},
            "ru_pay": {"prefixes": ("60",), "lengths": (16,)},
            "hipercard": {"prefixes": ("606282", "3841"), "lengths": (16,)},
            "elo": {"prefixes": ("401178", "401179", "438935", "457631", "457632",
                                   "431274", "451416", "457393", "504175", "636297",
                                   "506699", "5067", "65003", "65004", "65005"), "lengths": (16,)},
            "mir": {"prefixes": ("2200",), "lengths": (16,)},
        }
        
        # If card_type is not provided, try to deduce it.
        if not self.card_type:
            if card_number.startswith("4"):
                self.card_type = "visa"
            elif card_number.startswith(tuple(str(i) for i in range(51, 56))):
                self.card_type = "mastercard"
            elif card_number.startswith(("34", "37")):
                self.card_type = "american_express"
            elif (card_number.startswith("6011") or card_number.startswith("65") or 
                  card_number[:3] in tuple(str(i) for i in range(644, 650))):
                self.card_type = "discover"
            else:
                # You may extend this logic to cover more cases or require explicit entry.
                raise ValidationError("Card type could not be determined from the card number. Please specify it explicitly.")
        else:
            # If card_type is provided, verify its pattern.
            pattern = valid_patterns.get(self.card_type)
            if not pattern:
                raise ValidationError("Invalid card type specified.")
            if len(card_number) not in pattern["lengths"]:
                raise ValidationError(f"Invalid card number length for {self.card_type}. Expected lengths: {pattern['lengths']}.")
            if not any(card_number.startswith(prefix) for prefix in pattern["prefixes"]):
                raise ValidationError(f"Card number does not match the expected pattern for {self.card_type}. Expected prefixes: {pattern['prefixes']}.")
        
        # Optionally, if a full card number is provided (more than 8 digits), run Luhn checksum validation.
        if len(card_number) > 8 and all(ch.isdigit() for ch in card_number):
            if not luhn_checksum_is_valid(card_number):
                raise ValidationError("Card number failed Luhn checksum validation.")

    def save(self, *args, **kwargs):
        # Run full model validation before saving.
        self.full_clean()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.account.user} - {self.masked_number}"
    




class PaymentTransaction(models.Model):
    """
    Represents a payment transaction (e.g. purchase, refund, transfer)
    that is associated with an account and can involve a virtual card.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_id = ShortUUIDField(unique=True, length=15, prefix="TRX")
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, related_name="payment_transactions")
    virtual_card = models.ForeignKey(
        VirtualCard, on_delete=models.SET_NULL, null=True, blank=True, related_name="payment_transactions"
    )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=PAYMENT_TRANSACTION_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=PAYMENT_TRANSACTION_STATUS_CHOICES, default="pending")
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.transaction_id}"






class NFCDevice(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="nfc_devices")
    device_id = models.CharField(max_length=255, unique=True)
    device_name = models.CharField(max_length=255, blank=True)
    registered_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.device_id

class PaymentToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = ShortUUIDField(unique=True, length=20, prefix="TKN")
    account = models.ForeignKey(Account, on_delete=models.CASCADE, related_name="payment_tokens")
    virtual_card = models.ForeignKey(VirtualCard, on_delete=models.SET_NULL, null=True, blank=True, related_name="payment_tokens")
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    
    def __str__(self):
        return self.token




class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    notification_type = models.CharField(max_length=100, choices=NOTIFICATION_TYPE, default="none")
    amount = models.IntegerField(default=0)
    is_read = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    nid = ShortUUIDField(length=10, max_length=25, alphabet="abcdefghijklmnopqrstuvxyz")
    
    class Meta:
        ordering = ["-date"]
        verbose_name_plural = "Notification"

    def __str__(self):
        return f"{self.user} - {self.notification_type}"    