from rest_framework import serializers
from bluepay.models import (
    Transaction, 
    Notification ,
    VirtualCard,
    PaymentTransaction,
    NFCDevice,
    PaymentToken,
)

class TransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Transaction
        fields = '__all__'



class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = '__all__'



class VirtualCardSerializer(serializers.ModelSerializer):
    class Meta:
        model = VirtualCard
        fields = '__all__'



class PaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction
        fields = '__all__'



class NFCDeviceSerializer(serializers.ModelSerializer):
    class Meta:
        model = NFCDevice
        fields = '__all__'



class PaymentTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentToken
        fields = '__all__'


