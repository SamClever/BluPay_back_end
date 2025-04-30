from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
import random



class CustomUserManager(BaseUserManager):
    """
    Custom manager to handle user creation with email as the unique identifier.
    """
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email must be set')
        email = self.normalize_email(email)
        # If username is not provided, default it to the email
        extra_fields.setdefault('username', email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault('username', email)
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')
        return self.create_user(email, password, **extra_fields)



class User(AbstractUser):
    email = models.EmailField(unique=True)
    terms_accepted = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []  # Add other required fields if necessary

    objects = CustomUserManager()

    def __str__(self):
        return self.email
    




PURPOSE_CHOICES = (
    ('registration', 'Registration'),
    ('login', 'Login'),
    ('forgot_password', 'Forgot Password'),
)


def generate_otp():
    return str(random.randint(100000, 999999))

class OTPVerification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='otp_verifications')
    otp_code = models.CharField(max_length=6, default=generate_otp)
    purpose = models.CharField(max_length=20, choices=PURPOSE_CHOICES, default='registration')
    created_at = models.DateTimeField(auto_now_add=True)
    verified = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.user.email} - {self.otp_code} ({self.purpose})"
    

    class Meta:
        verbose_name = "OTP VERIFICATION"  # Singular name
        verbose_name_plural = "OTP VERIFICATIONS"  # Plural name
    
   


class DeactivationReason(models.Model):
    REASON_CHOICES = [
        ('not_accepted_widely', 'The payment system is not accepted at many locations'),
        ('security_concerns', 'I have concerns about payment security or data privacy'),
        ('technical_glitches', 'I encountered frequent technical issues or failed transactions'),
        ('switched_provider', 'I switched to a different payment provider'),
        ('limited_features', 'The system lacks features I need'),
        ('other', 'Other (please specify)'),
    ]

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    reason = models.CharField(max_length=50, choices=REASON_CHOICES)
    other_reason = models.TextField(blank=True, null=True)
    confirmed = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.email if self.user else 'Unknown'} - {self.reason}"