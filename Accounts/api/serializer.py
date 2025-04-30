from rest_framework import serializers
from userAccount.models import User
from django_countries.fields import CountryField
from Accounts.models import Account,KYC,IDENTITY_TYPE,GENDER
from datetime import date
from django.utils import timezone
import re
import phonenumbers
import pycountry
from phonenumbers import COUNTRY_CODE_TO_REGION_CODE, PhoneNumberFormat

PHONE_RE = re.compile(r'^\+?[0-9]{7,15}$')  # very basic E.164‐style check

############################################
# KYC Serializer
###########################################
class KYCSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYC
        fields = [
            'id',
            'user',
            'account',
            'First_name',
            'Last_name',
            'date_of_birth',  # required field
            'gender',
            'identity_type',
            'identity_image',
            'profile_image',
            'selfie_image',
            'biometric_hash',
            'address_line1',
            'address_line2',
            'city',
            'state',
            'zip_code',
            'country',
            'mobile',
            'date'
        ]
        read_only_fields = ("biometric_hash", "date")
        extra_kwargs = {
            'date_of_birth': {'required': True},
            # ... any other fields you need to require
        }





class KYCStep1Serializer(serializers.Serializer):
    identity_type = serializers.ChoiceField(choices=IDENTITY_TYPE)
    country       = serializers.CharField(max_length=100)

    def create(self, validated_data):
        """
        Called by serializer.save() when no instance is provided.
        """
        user = self.context['request'].user
        kyc, _ = KYC.objects.get_or_create(user=user)
        kyc.identity_type = validated_data['identity_type']
        kyc.country       = validated_data['country']
        kyc.save()
        return kyc

    def update(self, instance, validated_data):
        """
        (Optional) If you ever want to PATCH an existing KYC.
        """
        instance.identity_type = validated_data.get('identity_type', instance.identity_type)
        instance.country       = validated_data.get('country',       instance.country)
        instance.save()
        return instance

     


class KYCStep2Serializer(serializers.ModelSerializer):
    identity_image = serializers.ImageField(
        required=True,
        allow_empty_file=False,   # no zero‐byte uploads
        use_url=False              # we’ll build the URL in the view
    )

    class Meta:
        model = KYC
        fields = ['identity_image']
        extra_kwargs = {
            'identity_image': {'required': True}
        }


    def validate_identity_image(self, img):
        # 1) Check file type
        if img.content_type not in ('image/jpeg', 'image/png'):
            raise serializers.ValidationError("Only JPEG or PNG allowed.")
        # 2) Check size (5 MB max)
        max_size = 5 * 1024 * 1024
        if img.size > max_size:
            raise serializers.ValidationError("Image too large (max 5 MB).")
        return img



class KYCStep3Serializer(serializers.ModelSerializer):
    selfie_image = serializers.ImageField(
        required=True,
        allow_empty_file=False,
        use_url=False
    )

    class Meta:
        model = KYC
        fields = ['selfie_image']

    def validate_selfie_image(self, img):
        if img.content_type not in ('image/jpeg', 'image/png'):
            raise serializers.ValidationError("Only JPEG/PNG allowed.")
        if img.size > 5*1024*1024:
            raise serializers.ValidationError("Max size is 5 MB.")
        return img
    



class KYCStep4Serializer(serializers.ModelSerializer):
    gender = serializers.ChoiceField(choices=GENDER)
    mobile = serializers.CharField()

    class Meta:
        model = KYC
        fields = [
            'First_name', 'Last_name',
            'date_of_birth', 'gender',
            'address_line1', 'address_line2',
            'city', 'state', 'zip_code',
            'mobile',
        ]

    extra_kwargs = {
            'gender': {'choices': GENDER}
        }

    def validate_date_of_birth(self, date_of_birth):
        if date_of_birth >= date.today():
            raise serializers.ValidationError("Date of birth must be in the past.")
        return date_of_birth

    

    



class KYCStep5Serializer(serializers.ModelSerializer):
    # Build full URLs for the two images
    identity_image_url = serializers.SerializerMethodField()
    selfie_image_url   = serializers.SerializerMethodField()

    # Grab the user’s email off the related user object
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = KYC
        fields = [
            'identity_image_url',
            'selfie_image_url',
            'identity_type',
            'country',
            'First_name',
            'Last_name',
            'date_of_birth',
            'gender',
            'address_line1',
            'address_line2',
            'city',
            'state',
            'zip_code',
            'mobile',
            'email',
        ]

    def get_identity_image_url(self, obj):
        req = self.context.get('request')
        if obj.identity_image:
            return req.build_absolute_uri(obj.identity_image.url)
        return None

    def get_selfie_image_url(self, obj):
        req = self.context.get('request')
        if obj.selfie_image:
            return req.build_absolute_uri(obj.selfie_image.url)
        return None
    


############################################
# PIN SERIALIZER
###########################################
class SetPinSerializer(serializers.Serializer):
    pin = serializers.CharField(min_length=4, max_length=4)

    def validate_pin(self, pin):
        if not pin.isdigit():
            raise serializers.ValidationError("PIN must consist of 4 digits.")
        return pin
    





############################################
# FINGERPRINT SERIALIZER
###########################################
class EnableFingerprintSerializer(serializers.Serializer):
    """No inputs—just confirms the user wants to enable fingerprint."""
    # we return the generated secret in the view

class FingerprintLoginSerializer(serializers.Serializer):
    fingerprint_secret = serializers.CharField()



############################################
# FACEID SERIALIZER
###########################################
class EnableFaceIDSerializer(serializers.Serializer):
    """Nothing to pass in—client just requests to enable Face ID."""

class FaceIDLoginSerializer(serializers.Serializer):
    faceid_secret = serializers.CharField()



############################################
# ACCOUNTACTIVATIONS Serializer
###########################################
class AccountActivationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = [
            "account_number",
            "pin_number",
            "red_code",
            "account_status",
        ]
        read_only_fields = fields






def get_greeting():
    hour = timezone.localtime().hour
    if hour < 12:
        return "Good Morning"
    if hour < 18:
        return "Good Afternoon"
    return "Good Evening"

class UserProfileSerializer(serializers.Serializer):
    greeting = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    profile_image_url = serializers.SerializerMethodField()

    def get_greeting(self, obj):
        return get_greeting()

    def get_full_name(self, obj):
        user = obj
        name = user.get_full_name()
        return name if name else user.email

    def get_profile_image_url(self, obj):
        request = self.context['request']
        try:
            kyc = KYC.objects.get(user=obj)
            if kyc.profile_image:
                return request.build_absolute_uri(kyc.profile_image.url)
        except KYC.DoesNotExist:
            pass
        return None


class AccountSummarySerializer(serializers.Serializer):
    account_number = serializers.CharField(source='account.account_number')
    balance        = serializers.DecimalField(source='account.account_balance', max_digits=12, decimal_places=2)


class DashboardSerializer(serializers.Serializer):
    user          = UserProfileSerializer(source='*')
    account       = AccountSummarySerializer(source='*')
    quick_actions = serializers.ListField(child=serializers.DictField())
    services      = serializers.ListField(child=serializers.DictField())

    
############################################
# AccountSerializer
###########################################
class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account  # Specify the model to serialize
        fields = '__all__'  # This includes all fields from the Movie model
        
