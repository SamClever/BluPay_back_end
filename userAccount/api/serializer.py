from rest_framework import serializers
from userAccount.models import User

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User  # Specify the model to serialize
        fields = '__all__'  # This includes all fields from the Movie model
    