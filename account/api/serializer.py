from rest_framework import serializers
from userAccount.models import User

from account.models import Account,KYC



class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account  # Specify the model to serialize
        fields = '__all__'  # This includes all fields from the Movie model
        
class KycSerializer(serializers.ModelSerializer):
    class Meta:
        model = KYC  # Specify the model to serialize
        fields = '__all__'  # This includes all fields from the Movie model    
       