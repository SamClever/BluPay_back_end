from rest_framework import serializers
from .utils import validate_card_number, mask_card_number, detect_card_type, validate_expiration_date
from django.db.models import Q
from decimal import Decimal
from Accounts.models import *

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
        fields = [
            'id',
            'card_id',
            'card_token',
            'masked_number',
            'expiration_date',
            'created_at',
            'active',
            'default_card',
            'card_type',
        ]
        read_only_fields = ['id', 'card_id', 'created_at']
    
    def create(self, validated_data):
        # Get the current user and its account from the request context.
        user = self.context['request'].user
        from Accounts.models import Account  # avoid circular import errors
        account = Account.objects.get(user=user)
        validated_data['account'] = account
        
        # If this new card is set as default, unset any other default cards.
        if validated_data.get('default_card', False):
            VirtualCard.objects.filter(account=account, default_card=True).update(default_card=False)
        
        return super().create(validated_data)
    
    def update(self, instance, validated_data):
        user = self.context['request'].user
        from Accounts.models import Account
        account = Account.objects.get(user=user)
        
        # If updating the card to be the default, unset other cards.
        if validated_data.get('default_card', False):
            VirtualCard.objects.filter(account=account, default_card=True).exclude(id=instance.id).update(default_card=False)
        
        return super().update(instance, validated_data)
    



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




class AccountSearchSerializer(serializers.ModelSerializer):
    first_name = serializers.CharField(source='kyc.First_name', read_only=True)
    last_name  = serializers.CharField(source='kyc.Last_name',  read_only=True)
    email      = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Account
        fields = [
            'account_number',
            'account_id',
            'email',
            'account_balance',
            'first_name',
            'last_name',
        ]



class InitiateTransferSerializer(serializers.Serializer):
    account_number = serializers.CharField()
    amount         = serializers.DecimalField(max_digits=12, decimal_places=2)
    description    = serializers.CharField(allow_blank=True, required=False)

    def validate_account_number(self, value):
        try:
            return Account.objects.get(
                Q(account_number=value) | Q(account_id=value)
            )
        except Account.DoesNotExist:
            raise serializers.ValidationError("Account does not exist.")

    def validate_amount(self, value):
        if value <= Decimal('0.00'):
            raise serializers.ValidationError("Amount must be positive.")
        return value

    def validate(self, attrs):
        recipient_account = attrs['account_number']
        sender_account = self.context['request'].user.account

        if sender_account.account_balance < attrs['amount']:
            raise serializers.ValidationError("Insufficient funds.")
        if recipient_account == sender_account:
            raise serializers.ValidationError("Cannot transfer to your own account.")
        attrs['recipient_account'] = recipient_account
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        tx = Transaction.objects.create(
            user=user,
            amount=validated_data['amount'],
            description=validated_data.get('description', ''),
            sender=user,
            reciver=validated_data['recipient_account'].user,
            sender_account=user.account,
            reciver_account=validated_data['recipient_account'],
            transaction_type="transfer",
            status="processing",
        )
        return tx


class TransactionSerializer(serializers.ModelSerializer):
    sender_account_number   = serializers.CharField(source='sender_account.account_number', read_only=True)
    reciver_account_number  = serializers.CharField(source='reciver_account.account_number', read_only=True)
    class Meta:
        model = Transaction
        fields = [
            'transaction_id',
            'amount',
            'description',
            'status',
            'transaction_type',
            'sender_account_number',
            'reciver_account_number',
            'date',
        ]


class ConfirmTransferSerializer(serializers.Serializer):
    pin_number = serializers.CharField()

    def validate_pin_number(self, value):
        user = self.context['request'].user
        if value != user.account.pin_number:
            raise serializers.ValidationError("Incorrect PIN.")
        return value

    def validate(self, attrs):
        """
        Expecting .context['transaction'] to be set by the view.
        """
        tx = self.context.get('transaction')
        if not tx:
            raise serializers.ValidationError("Transaction not found.")
        if tx.status != 'processing':
            raise serializers.ValidationError("Transaction cannot be confirmed.")
        attrs['transaction'] = tx
        return attrs

    def save(self):
        tx = self.validated_data['transaction']
        sender_ac = tx.sender_account
        rec_ac    = tx.reciver_account

        # finalize
        tx.status = "completed"
        tx.save()

        sender_ac.account_balance -= tx.amount
        sender_ac.save()

        rec_ac.account_balance += tx.amount
        rec_ac.save()

        # create notifications
        
        Notification.objects.create(
            user=tx.reciver,
            notification_type="Credit Alert",
            amount=tx.amount
        )
        Notification.objects.create(
            user=tx.sender,
            notification_type="Debit Alert",
            amount=tx.amount
        )

        return tx