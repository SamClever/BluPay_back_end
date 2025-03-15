from django.db import models
import uuid
from userAccount.models import User
from shortuuid.django_fields import ShortUUIDField
from django.db.models.signals import post_save
from django.dispatch import receiver

ACCOUNT_STATUS = (
    ("active", "Active"),
    ("pending", "Pending"),
    ("inactive", "Inactive"),  # Changed "in-active" to "inactive" for consistency
)

GENDER = (
    ("male", "Male"),
    ("female", "Female"),
    ("other", "Other")
)

IDENTITY_TYPE = (
    ("national_id_card", "National ID Card"),
    ("drivers_licence", "Drivers Licence"),
    ("international_passport", "International Passport")
)

def user_directory_path(instance, filename):
    ext = filename.split(".")[-1]
    filename = f"{instance.id}_{ext}"
    return f"user_{instance.user.id}/{filename}"

class Account(models.Model):
    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    account_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    account_number = ShortUUIDField(
        length=10, unique=True, max_length=25, prefix="217", alphabet="1234567890"
    )
    account_id = ShortUUIDField(
        length=7, unique=True, max_length=25, prefix="DEX", alphabet="1234567890"
    )
    pin_number = ShortUUIDField(
        length=4, unique=True, max_length=7, alphabet="1234567890"
    )
    red_code = ShortUUIDField(
        length=10, unique=True, max_length=20, prefix="217", alphabet="abcdefghi1234567890"
    )
    account_status = models.CharField(max_length=100, choices=ACCOUNT_STATUS, default="inactive")
    date = models.DateTimeField(auto_now_add=True)
    kyc_submitted = models.BooleanField(default=False)
    kyc_confirmed = models.BooleanField(default=False)
    recommended_by = models.ForeignKey(
        User,
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="recommended_accounts"  # Updated related_name for clarity
    )

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.user}"

@receiver(post_save, sender=User)
def create_account(sender, instance, created, **kwargs):
    if created:
        Account.objects.create(user=instance)


class KYC(models.Model):
    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    account = models.OneToOneField(Account, on_delete=models.CASCADE, null=True, blank=True)
    full_name = models.CharField(max_length=1000)
    image = models.ImageField(upload_to=user_directory_path, default="default.jpg")
    gender = models.CharField(choices=GENDER, max_length=40)
    identity_type = models.CharField(choices=IDENTITY_TYPE, max_length=140)
    identity_image = models.ImageField(upload_to=user_directory_path, null=True, blank=True)
    date_of_birth = models.DateField()  # Changed to DateField
    signature = models.ImageField(upload_to=user_directory_path)

    # Address
    country = models.CharField(max_length=100)
    state = models.CharField(max_length=100)
    city = models.CharField(max_length=100)

    # Contact Detail
    mobile = models.CharField(max_length=1000)
    fax = models.CharField(max_length=1000)
    date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.user}"
