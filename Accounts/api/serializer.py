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



     

    
class KYCIdentityUploadSerializer(serializers.ModelSerializer):
    country = CountryField()
    required_documents = serializers.SerializerMethodField()
    
    class Meta:
        model = KYC
        fields = [
            'identity_image',
           
        ]
        read_only_fields = ['id', 'required_documents']
    
    def get_required_documents(self, obj):
        return {
            'front': True,
            'back': obj.identity_type in ['national_id_card', 'drivers_license'],
            'selfie': True
        }
    
    def validate(self, data):
        identity_type = data.get('identity_type')
        
        # Validate back image is required for certain ID types
        if identity_type in ['national_id_card', 'drivers_license']:
            if 'identity_document_back' not in data or not data['identity_document_back']:
                raise serializers.ValidationError(
                    "Back side of document is required for this ID type"
                )
        
        return data

    def validate_identity_document_front(self, value):
        return self._validate_image_file(value, "Front side")
    
    def validate_identity_document_back(self, value):
        if value:  # Only validate if back image is provided
            return self._validate_image_file(value, "Back side")
        return value
    
    def validate_selfie_with_id(self, value):
        return self._validate_image_file(value, "Selfie")
    
    def _validate_image_file(self, value, field_name):
        # Validate file size (max 5MB)
        max_size = 5 * 1024 * 1024
        if value.size > max_size:
            raise serializers.ValidationError(
                f"{field_name} image size must be less than 5MB"
            )
        
        # Validate file type
        valid_extensions = ['.jpg', '.jpeg', '.png']
        if not any(value.name.lower().endswith(ext) for ext in valid_extensions):
            raise serializers.ValidationError(
                f"{field_name} must be a JPG or PNG image"
            )
        
        return value


############################################
# AccountSerializer
###########################################
class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account  # Specify the model to serialize
        fields = '__all__'  # This includes all fields from the Movie model
        
