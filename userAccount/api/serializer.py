from rest_framework import serializers
from userAccount.models import User
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password






User = get_user_model()

class UserRegistrationSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        required=True,
        validators=[validate_password]
    )
    terms_accepted = serializers.BooleanField(write_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'password', 'terms_accepted')
        extra_kwargs = {
            'password': {'write_only': True}
        }

    def validate_terms_accepted(self, value):
        if value is not True:
            raise serializers.ValidationError("You must accept our Privacy Policy to register.")
        return value

    def create(self, validated_data):
        validated_data.pop('terms_accepted')
        # Ensure username is set; if not, use email as username
        if not validated_data.get('username'):
            validated_data['username'] = validated_data.get('email')
        user = User.objects.create_user(**validated_data)
        return user



class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User  # Specify the model to serialize
        fields = '__all__'  # This includes all fields from the Movie model
    