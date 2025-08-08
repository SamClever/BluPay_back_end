from django.db import models
import uuid, hashlib
from userAccount.models import User
from shortuuid.django_fields import ShortUUIDField
from django.db.models.signals import post_save
from django.dispatch import receiver
from typing import Dict, Optional, Tuple
from decimal import Decimal


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


    # Biometric authentication fields
    fingerprint_enabled = models.BooleanField(default=False)
    fingerprint_secret  = models.CharField(max_length=64, null=True, blank=True)
    faceid_enabled = models.BooleanField(default=False)
    faceid_secret  = models.CharField(max_length=64, null=True, blank=True)

    # Transaction limits based on KYC status
    daily_limit = models.DecimalField(max_digits=12, decimal_places=2, default=50000.00)
    monthly_limit = models.DecimalField(max_digits=12, decimal_places=2, default=200000.00)
    single_transaction_limit = models.DecimalField(max_digits=12, decimal_places=2, default=20000.00)

    recommended_by = models.ForeignKey(
        User,
        on_delete=models.DO_NOTHING,
        blank=True,
        null=True,
        related_name="recommended_accounts"
    )

    class Meta:
        ordering = ['-date']

    def __str__(self):
        return f"{self.user.email} - {self.account_number}"

    @property
    def has_kyc_attachments(self):
        """Check if account has KYC with required attachments"""
        try:
            kyc = self.kyc
            return bool(kyc.identity_image and kyc.selfie_image)
        except KYC.DoesNotExist:
            return False

    @property
    def kyc_completion_percentage(self):
        """Calculate KYC completion percentage"""
        try:
            kyc = self.kyc
            total_fields = 12
            completed_fields = 0
            
            if kyc.First_name: completed_fields += 1
            if kyc.Last_name: completed_fields += 1
            if kyc.date_of_birth: completed_fields += 1
            if kyc.gender: completed_fields += 1
            if kyc.identity_type: completed_fields += 1
            if kyc.identity_image: completed_fields += 1
            if kyc.selfie_image: completed_fields += 1
            if kyc.address_line1: completed_fields += 1
            if kyc.city: completed_fields += 1
            if kyc.state: completed_fields += 1
            if kyc.country: completed_fields += 1
            if kyc.mobile: completed_fields += 1
            
            return round((completed_fields / total_fields) * 100, 2)
        except KYC.DoesNotExist:
            return 0.0

    def update_transaction_limits(self):
        """Update transaction limits based on KYC status"""
        if self.kyc_confirmed:
            self.daily_limit = Decimal('1000000.00')  # 1M TZS
            self.monthly_limit = Decimal('10000000.00')  # 10M TZS
            self.single_transaction_limit = Decimal('1000000.00')  # 1M TZS
        elif self.kyc_submitted:
            self.daily_limit = Decimal('100000.00')  # 100K TZS
            self.monthly_limit = Decimal('1000000.00')  # 1M TZS
            self.single_transaction_limit = Decimal('50000.00')  # 50K TZS
        else:
            self.daily_limit = Decimal('50000.00')  # 50K TZS
            self.monthly_limit = Decimal('200000.00')  # 200K TZS
            self.single_transaction_limit = Decimal('20000.00')  # 20K TZS
        self.save()

@receiver(post_save, sender=User)
def create_account(sender, instance, created, **kwargs):
    if created:
        Account.objects.create(user=instance)


class KYC(models.Model):
    id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    account = models.OneToOneField(Account, on_delete=models.CASCADE, null=True, blank=True, related_name="kyc")
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

    @property
    def has_required_attachments(self):
        """Check if KYC has all required attachments"""
        return bool(self.identity_image and self.selfie_image)

    @property
    def is_complete(self):
        """Check if KYC is complete with all required fields"""
        required_fields = [
            self.First_name, self.Last_name, self.date_of_birth,
            self.gender, self.identity_type, self.identity_image,
            self.selfie_image, self.address_line1, self.city,
            self.state, self.country, self.mobile
        ]
        return all(field for field in required_fields)

    def save(self, *args, **kwargs):
        # Auto-link to account if not already linked
        if not self.account and self.user:
            try:
                self.account = Account.objects.get(user=self.user)
            except Account.DoesNotExist:
                pass
        
        # Compute biometric hash if selfie_image is provided
        if self.selfie_image:
            try:
                self.selfie_image.open()
                data = self.selfie_image.read()
                self.biometric_hash = hashlib.sha256(data).hexdigest()
            except Exception as e:
                self.biometric_hash = None
        
        super().save(*args, **kwargs)
        
        # Update account transaction limits when KYC status changes
        if self.account:
            self.account.update_transaction_limits()
