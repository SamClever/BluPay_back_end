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
            'face_verification_image',
            'biometric_hash',
            'address_line1',
            'address_line2',
            'city',
            'state',
            'zip_code',
            'country',
            'mobile',
            'fax',
            'date'
        ]
        read_only_fields = ("biometric_hash", "date")
        extra_kwargs = {
            'date_of_birth': {'required': True},
            # ... any other fields you need to require
        }

        

############################################
# AccountSerializer
###########################################
class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account  # Specify the model to serialize
        fields = '__all__'  # This includes all fields from the Movie model
        
