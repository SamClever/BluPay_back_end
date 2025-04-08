from django.db import models
import uuid, hashlib
from userAccount.models import User
from shortuuid.django_fields import ShortUUIDField
from django.db.models.signals import post_save
from django.dispatch import receiver

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
    # full_name = models.CharField(max_length=1000)
    

    # Personal Information
    First_name = models.CharField(max_length=255)
    Last_name = models.CharField(
        max_length=255, 
        blank=True, 
        null=True, 
        help_text="Optional: Enter your family or traditional name if applicable"
    )
    date_of_birth = models.DateField()
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
    face_verification_image = models.ImageField(
        upload_to=user_directory_path, 
        null=True, 
        blank=True,
        help_text="Image used for face verification"
    )
    


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
    fax = models.CharField(max_length=20, null=True, blank=True)
    
    date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-date']
        verbose_name = "KYC Record"
        verbose_name_plural = "KYC Records"
    
    def __str__(self):
        return f"KYC for {self.user.email}"
    


    def save(self, *args, **kwargs):
        # Compute biometric hash if face_verification_image is provided
        if self.face_verification_image:
            try:
                # Open the image file; ensure the file is read in binary mode.
                self.face_verification_image.open()
                data = self.face_verification_image.read()
                self.biometric_hash = hashlib.sha256(data).hexdigest()
            except Exception as e:
                # Optionally, log error or set biometric_hash to None if processing fails
                self.biometric_hash = None
        super().save(*args, **kwargs)
