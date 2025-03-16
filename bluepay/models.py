from django.db import models
import uuid
from shortuuid.django_fields import ShortUUIDField
from userAccount.models import User
from account.models import Account
# Create your models here.



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
    ("master", "master"),
    ("visa", "visa"),
    ("verve", "verve"),

)


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

)

class Transaction(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_id = ShortUUIDField(unique=True, length=15, max_length=20, prefix="TRN")
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="user")
    amount = models.DecimalField(max_digits=12, decimal_places=2,default=0.00)
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
    masked_number = models.CharField(max_length=20)
    expiration_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.account.user} - {self.masked_number}"
    


class PaymentTransaction(models.Model):
    TRANSACTION_TYPE_CHOICES = (
        ('purchase', 'Purchase'),
        ('refund', 'Refund'),
        ('transfer', 'Transfer'),
    )
    TRANSACTION_STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    )
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_id = ShortUUIDField(unique=True, length=15, prefix="TRX")
    account = models.ForeignKey(Account, on_delete=models.SET_NULL, null=True, related_name="transactions")
    virtual_card = models.ForeignKey(VirtualCard, on_delete=models.SET_NULL, null=True, blank=True, related_name="transactions")
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    transaction_type = models.CharField(max_length=20, choices=TRANSACTION_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=TRANSACTION_STATUS_CHOICES, default="pending")
    description = models.TextField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.transaction_id



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