from django.db import models
import uuid, hashlib
from userAccount.models import User
from shortuuid.django_fields import ShortUUIDField
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.hashers import make_password, check_password
from BlupayBackend.settings import CURRENCY_CHOICES



ACCOUNT_STATUS = (
    ("active", "Active"),
    ("pending", "Pending"),
    ("inactive", "Inactive"),
)

GENDER = (
    ("male", "Male"),
    ("female", "Female"),
    ("other", "Other"),
)

IDENTITY_TYPE = (
    ("national_id_card", "National ID Card"),
    ("drivers_licence", "Drivers Licence"),
    ("international_passport", "International Passport"),
)


def user_directory_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{instance.id}_{ext}"
    # If instance has a user, use its id; otherwise, use a default folder.
    if hasattr(instance, 'user') and instance.user:
        return f"user_{instance.user.id}/{filename}"
    return f"user_default/{filename}"


# -----------------------------------------------------------------------------

class Account(models.Model):
    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    account_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    stripe_customer_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
       help_text="The Stripe Customer ID for this account"
    )
    
    default_currency_code = models.CharField(
        max_length=3,
        choices=CURRENCY_CHOICES,
        default='TZS',
        help_text="ISO 4217 currency code for this account"
    )
    account_id = ShortUUIDField(
        length=7, unique=True, max_length=25, prefix="DEX", alphabet="1234567890"
    )

    pin_hash            = models.CharField(max_length=128, blank=True)

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


    # Add these two fields:
    fingerprint_enabled = models.BooleanField(default=False)
    fingerprint_secret  = models.CharField(max_length=64, null=True, blank=True)


    faceid_enabled = models.BooleanField(default=False)
    faceid_secret  = models.CharField(max_length=64, null=True, blank=True)

    recommended_by = models.ForeignKey(
        User,
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="recommended_accounts"  # Updated related_name for clarity
    )

    def set_pin(self, raw_pin):
        """
        Hash & store the PIN. Also preserve a random 4-digit PIN_number
        if you still want to display/test a user-visible PIN.
        """
        self.pin_hash   = make_password(raw_pin)
        # Optionally generate a new short display PIN:
        self.pin_number = raw_pin[-4:]
        # (or leave pin_number untouched if you don't need it)
        return self.pin_hash

    def check_pin(self, raw_pin) -> bool:
        """
        Returns True if the provided raw_pin matches.
        """
        if not self.pin_hash:
            return False
        return check_password(raw_pin, self.pin_hash)

    class Meta:
        ordering = ['-date']

    @property
    def wallet_number(self):
        """
        Derive the wallet number from the primary virtual card's masked_number.
        """
        primary_card = self.virtual_cards.filter(default_card=True).first()
        if not primary_card:
            primary_card = self.virtual_cards.first()
        return primary_card.masked_number if primary_card else None
    
    

    def __str__(self):
        return f"Wallet {self.wallet_number} ({self.user.email})"

@receiver(post_save, sender=User)
def create_account(sender, instance, created, **kwargs):
    if created:
        Account.objects.create(user=instance)


class KYC(models.Model):
    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    account = models.OneToOneField(Account, on_delete=models.CASCADE, null=True, blank=True)
    # full_name = models.CharField(max_length=1000)
    

    # Personal Information
    First_name = models.CharField(max_length=255)
    Last_name = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="Optional: Enter your family or traditional name if applicable"
    )
    date_of_birth = models.DateField(null=True, blank=True)
    gender = models.CharField(choices=GENDER, max_length=10)
    
    # Identity Documents
    identity_type = models.CharField(choices=IDENTITY_TYPE, max_length=50)
    identity_image = models.ImageField(upload_to=user_directory_path, null=True, blank=True)
    
    # Verification Images
    profile_image = models.ImageField(
        upload_to=user_directory_path, 
        default="default.jpg",
        help_text="A clear picture of your face"
    )

    selfie_image = models.ImageField(
        upload_to=user_directory_path, 
        null=True, 
        blank=True,
        help_text="Image used for face verification"
    )

    face_verified     = models.BooleanField(default=False)
    face_match_score  = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    


    biometric_hash = models.CharField(
        max_length=64,
        blank=True,
        null=True,
        help_text="SHA-256 hash of the face verification image"
    )
    
    
    # Address Information
    address_line1 = models.CharField(max_length=255, blank=True)
    address_line2 = models.CharField(max_length=255, blank=True)
    city = models.CharField(max_length=100, blank=True)
    state = models.CharField(max_length=100, blank=True)
    zip_code = models.CharField(max_length=20, blank=True)
    country = models.CharField(max_length=100, blank=True)
    
    # Contact Details
    mobile = models.CharField(max_length=20)
    
    
    date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date']
        verbose_name = "KYC Record"
        verbose_name_plural = "KYC Records"
    
    def __str__(self):
        return f"KYC for {self.user.email}"
    


    def save(self, *args, **kwargs):
        # Compute biometric hash if selfie_image is provided
        if self.selfie_image:
            try:
                # Open the image file; ensure the file is read in binary mode.
                self.selfie_image.open()
                data = self.selfie_image.read()
                self.biometric_hash = hashlib.sha256(data).hexdigest()
            except Exception as e:
                # Optionally, log error or set biometric_hash to None if processing fails
                self.biometric_hash = None
        super().save(*args, **kwargs)
