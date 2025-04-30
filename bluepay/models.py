from django.db import models
import uuid
from django.core.exceptions import ValidationError
import re
from shortuuid.django_fields import ShortUUIDField
from userAccount.models import User
from Accounts.models import Account
from decimal import Decimal
from django.conf import settings
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

    # ─── Wallet Funding ────────────────────────────────────────────────────────
    ("top_up_initiated",     "Top-Up Initiated"),
    ("top_up_success",       "Top-Up Successful"),
    ("top_up_failed",        "Top-Up Failed"),


    # ─── Withdrawals ─────────────────────────────────────────────────────────
    ("withdrawal_initiated", "Withdrawal Initiated"),
    ("withdrawal_success",   "Withdrawal Successful"),
    ("withdrawal_failed",    "Withdrawal Failed"),


    # ─── Payments & Transfers ─────────────────────────────────────────────────
    ("payment_initiated",    "Payment Initiated"),
    ("payment_success",      "Payment Successful"),
    ("payment_failed",       "Payment Failed"),
    ("transfer_initiated",   "Transfer Initiated"),
    ("transfer_success",     "Transfer Successful"),
    ("transfer_failed",      "Transfer Failed"),
    ("refund_initiated",     "Refund Initiated"),
    ("refund_success",       "Refund Processed"),
    ("refund_failed",        "Refund Failed"),


    # ─── NFC & Contactless ────────────────────────────────────────────────────
    ("nfc_tap_success",           "NFC Tap Successful"),
    ("nfc_tap_failed",            "NFC Tap Failed"),
    ("contactless_success",       "Contactless Payment Successful"),
    ("contactless_failed",        "Contactless Payment Declined"),


    # ─── Balance & Statements ─────────────────────────────────────────────────
    ("balance_low_alert",         "Low Balance Alert"),
    ("balance_updated",           "Balance Updated"),
    ("daily_summary_ready",       "Daily Summary Ready"),
    ("monthly_statement_ready",   "Monthly Statement Ready"),


    # ─── Security & Fraud ─────────────────────────────────────────────────────
    ("new_device_login",          "New Device Login Detected"),
    ("password_changed",          "Password Changed"),
    ("pin_changed",               "PIN Changed"),
    ("suspicious_activity",       "Suspicious Activity Alert"),
    ("fraud_alert",               "Fraud Alert"),


    # ─── KYC & Account ────────────────────────────────────────────────────────
    ("kyc_submitted",             "KYC Submitted"),
    ("kyc_approved",              "KYC Approved"),
    ("kyc_rejected",              "KYC Rejected"),
    ("account_locked",            "Account Locked"),
    ("account_unlocked",          "Account Unlocked"),


    # ─── Promotions & Updates ─────────────────────────────────────────────────
    ("promo_offer",               "New Promotional Offer"),
    ("discount_available",        "Discount Available"),
    ("app_update_available",      "App Update Available"),


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


CURRENCY_CHOICES = [
    ('USD', 'US Dollar'),
    ('TZS', 'Tanzanian Shilling'),
    # ('EUR', 'Euro'),
    # ('GBP', 'British Pound'),
]


# -----------------------------------------------------------------------------
# Models
# -----------------------------------------------------------------------------

class Transaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_id = ShortUUIDField(unique=True, length=15, max_length=20, prefix="TRN")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="user")
    amount = models.DecimalField(max_digits=12, decimal_places=2,default=0.00)
    currency_code = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='TZS',
        help_text="ISO 4217 currency code"
    )

    description = models.CharField(max_length=1000, null=True, blank=True)

    reciver = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="reciver")
    sender = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="sender")

    reciver_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, related_name="reciver_account")
    sender_account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, related_name="sender_account")

    status = models.CharField(choices=TRANSACTION_STATUS ,max_length=100, default="pending")
    transaction_type = models.CharField(choices=TRANSACTION_TYPE ,max_length=100, default="none")


    date = models.DateTimeField(auto_now_add=True)
    update = models.DateTimeField(auto_now_add=False, null=True, blank=True)


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

    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    default_card = models.BooleanField(default=False)

    card_type = models.CharField(max_length=20, choices=CARD_TYPE, blank=True, null=True)


    # def clean(self):
    #     """
    #     Sanitizes and validates the card data:
    #       - Strips spaces and hyphens.
    #       - Ensures the card number is numeric.
    #       - Attempts to deduce the card type if not provided.
    #       - Validates the card number based on expected lengths, prefix patterns, and Luhn check.
    #     """
    #     # Sanitize the card number: remove spaces and hyphens.
    #     card_number = self.masked_number.replace(" ", "").replace("-", "")
        
    #     if not card_number.isdigit():
    #         raise ValidationError("Card number must contain only digits (spaces and dashes are allowed).")
        
    #     # Define the expected patterns for each card type.
    #     valid_patterns = {
    #         "visa": {"prefixes": ("4",), "lengths": (13, 16, 19)},
    #         "mastercard": {"prefixes": tuple(str(i) for i in range(51, 56)), "lengths": (16,)},
    #         "american_express": {"prefixes": ("34", "37"), "lengths": (15,)},
    #         "discover": {"prefixes": ("6011", "65") + tuple(str(i) for i in range(644, 650)), "lengths": (16,)},
    #         "diners_club": {"prefixes": ("300", "301", "302", "303", "304", "305", "36", "38"), "lengths": (14,)},
    #         "jcb": {"prefixes": ("35",), "lengths": (16,)},
    #         "unionpay": {"prefixes": ("62",), "lengths": (16, 17, 18, 19)},
    #         "maestro": {"prefixes": ("50", "56", "57", "58", "6304", "67"), "lengths": tuple(range(12, 20))},
    #         "ru_pay": {"prefixes": ("60",), "lengths": (16,)},
    #         "hipercard": {"prefixes": ("606282", "3841"), "lengths": (16,)},
    #         "elo": {"prefixes": ("401178", "401179", "438935", "457631", "457632",
    #                                "431274", "451416", "457393", "504175", "636297",
    #                                "506699", "5067", "65003", "65004", "65005"), "lengths": (16,)},
    #         "mir": {"prefixes": ("2200",), "lengths": (16,)},
    #     }
        
    #     # If card_type is not provided, try to deduce it.
    #     if not self.card_type:
    #         if card_number.startswith("4"):
    #             self.card_type = "visa"
    #         elif card_number.startswith(tuple(str(i) for i in range(51, 56))):
    #             self.card_type = "mastercard"
    #         elif card_number.startswith(("34", "37")):
    #             self.card_type = "american_express"
    #         elif (card_number.startswith("6011") or card_number.startswith("65") or 
    #               card_number[:3] in tuple(str(i) for i in range(644, 650))):
    #             self.card_type = "discover"
    #         else:
    #             # You may extend this logic to cover more cases or require explicit entry.
    #             raise ValidationError("Card type could not be determined from the card number. Please specify it explicitly.")
    #     else:
    #         # If card_type is provided, verify its pattern.
    #         pattern = valid_patterns.get(self.card_type)
    #         if not pattern:
    #             raise ValidationError("Invalid card type specified.")
    #         if len(card_number) not in pattern["lengths"]:
    #             raise ValidationError(f"Invalid card number length for {self.card_type}. Expected lengths: {pattern['lengths']}.")
    #         if not any(card_number.startswith(prefix) for prefix in pattern["prefixes"]):
    #             raise ValidationError(f"Card number does not match the expected pattern for {self.card_type}. Expected prefixes: {pattern['prefixes']}.")
        
    #     # Optionally, if a full card number is provided (more than 8 digits), run Luhn checksum validation.
    #     if len(card_number) > 8 and all(ch.isdigit() for ch in card_number):
    #         if not luhn_checksum_is_valid(card_number):
    #             raise ValidationError("Card number failed Luhn checksum validation.")

    def save(self, *args, **kwargs):
        # Run full model validation before saving.
        self.full_clean()
        super().save(*args, **kwargs)

    def clean(self):
        # if masked_number contains anything but digits, spaces or hyphens,
        # assume it’s a “masked” display string and skip full validation.
        if re.search(r"[^\d\s-]", self.masked_number):
            return

        # otherwise run your existing sanitization & Luhn checks…
        card_number = self.masked_number.replace(" ", "").replace("-", "")
    
    def __str__(self):
        return f"{self.account.user} - {self.masked_number}"
    

class PaymentTransaction(models.Model):
    NONE      = "none"
    TOP_UP    = "top_up"
    WITHDRAW  = "withdraw"
    NFC_PAY   = "nfc_pay"

    TXN_TYPES = [
        (TOP_UP,   "Top Up"),
        (WITHDRAW, "Withdraw"),
        (NFC_PAY,  "NFC Payment"),
        (NONE,     "None"),
    ]

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
    txn_type   = models.CharField(max_length=10, choices=TXN_TYPES, default=NONE,)
    transaction_type = models.CharField(max_length=20, choices=PAYMENT_TRANSACTION_TYPE_CHOICES, default="purchase")
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
    token      = ShortUUIDField(unique=True, length=20, prefix="TAP")
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
    message = models.TextField(blank=True)
    is_read = models.BooleanField(default=False)
    date = models.DateTimeField(auto_now_add=True)
    nid = ShortUUIDField(length=10, max_length=25, alphabet="abcdefghijklmnopqrstuvxyz")
    
    class Meta:
        ordering = ["-date"]
        verbose_name_plural = "Notification"

    def __str__(self):
        return f"{self.user} - {self.notification_type}"
    



class NotificationSettings(models.Model):
    user              = models.OneToOneField(User, on_delete=models.CASCADE, related_name="notification_settings")
    general           = models.BooleanField(default=True)
    sound             = models.BooleanField(default=False)
    vibrate           = models.BooleanField(default=False)
    app_updates       = models.BooleanField(default=True)
    bill_reminder     = models.BooleanField(default=True)
    promotion         = models.BooleanField(default=False)
    discounts         = models.BooleanField(default=False)
    payment_request   = models.BooleanField(default=True)
    new_service       = models.BooleanField(default=False)
    new_tips          = models.BooleanField(default=False)
    updated_at        = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Notification Settings"

    def __str__(self):
        return f"Notif. settings for {self.user}"
    


class SecuritySetting(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="security_setting",
    )

    remember_me   = models.BooleanField(default=True)
    face_id       = models.BooleanField(default=False)
    biometric_id  = models.BooleanField(default=False)

    # Google Authenticator: store the TOTP secret if set up
    ga_secret     = models.CharField(max_length=32, blank=True, null=True)
    ga_enabled    = models.BooleanField(default=False)

    updated_at    = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"SecuritySetting for {self.user.email}"
    


