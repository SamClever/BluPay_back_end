from rest_framework import serializers
from userAccount.models import User

from Accounts.models import Account,KYC







############################################
# KYC Serializer
###########################################


class KYCSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYC
        fields = [
            # Personal Information
            'full_name', 'Last_name', 'date_of_birth', 'gender',
            # Identity Documents
            'identity_type', 'identity_image',
            # Verification Images
            'profile_image', 'face_verification_image' 'biometric_hash',
            # Address Information
            'address_line1', 'address_line2', 'city', 'state', 'zip_code', 'country',
            # Contact Details
            'mobile', 'fax',
            # Metadata (read-only)
            'date'
        ]
        read_only_fields = ('biometric_hash', 'date')

class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account  # Specify the model to serialize
        fields = '__all__'  # This includes all fields from the Movie model
        
class KycSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYC  # Specify the model to serialize
        fields = '__all__'  # This includes all fields from the Movie model    
       