from rest_framework import serializers
from .utils import validate_card_number, mask_card_number, detect_card_type, validate_expiration_date
from django.db.models import Q
from decimal import Decimal
from Accounts.models import *

import re
from bluepay.models import (
    Transaction, 
    Notification ,
    VirtualCard,
    PaymentTransaction,
    NFCDevice,
    PaymentToken,
    Payment, 
    PaymentStatusHistory, 
    MobileMoneyProvider,
    Payout,
    PayoutStatusHistory,
    PayoutWebhook,
    



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
    profile_image = serializers.SerializerMethodField()

    class Meta:
        model = Account
        fields = [
            'account_number',
            'account_id',
            'email',
            'first_name',
            'last_name',
            "profile_image",
        ]
        
    def get_profile_image(self, obj):
        kyc = KYC.objects.filter(account=obj).first()
        request = self.context.get("request")
        if kyc and kyc.profile_image:
            if request:
                return request.build_absolute_uri(kyc.profile_image.url)
            return kyc.profile_image.url
        return None



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
    





class MobileMoneyProviderSerializer(serializers.ModelSerializer):
    class Meta:
        model = MobileMoneyProvider
        fields = ['id', 'name', 'code', 'country', 'is_active']


class PaymentStatusHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentStatusHistory
        fields = ['id', 'previous_status', 'new_status', 'message', 'created_at']

class PaymentSerializer(serializers.ModelSerializer):
    status_history = PaymentStatusHistorySerializer(many=True, read_only=True)
    mobile_provider_name = serializers.CharField(source='mobile_provider.name', read_only=True)
    account_number = serializers.CharField(source='account.account_number', read_only=True)
    user_email = serializers.CharField(source='account.user.email', read_only=True)
    
    class Meta:
        model = Payment
        fields = [
            'id', 'payment_reference', 'order_reference', 'clickpesa_transaction_id',
            'account', 'account_number', 'user_email', 'transaction_type', 'payment_method',
            'mobile_provider', 'mobile_provider_name', 'amount', 'currency',
            'collected_amount', 'collected_currency', 'status', 'message',
            'customer_name', 'customer_phone', 'customer_email', 'client_id',
            'metadata', 'created_at', 'updated_at', 'clickpesa_created_at',
            'clickpesa_updated_at', 'status_history'
        ]
        read_only_fields = [
            'id', 'clickpesa_transaction_id', 'collected_amount', 'collected_currency',
            'status', 'message', 'client_id', 'created_at', 'updated_at',
            'clickpesa_created_at', 'clickpesa_updated_at'
        ]

class PaymentStatusQuerySerializer(serializers.Serializer):
    """Serializer for payment status query response"""
    id = serializers.CharField()
    status = serializers.ChoiceField(choices=['SUCCESS', 'SETTLED', 'PROCESSING', 'PENDING', 'FAILED'])
    payment_reference = serializers.CharField(source='paymentReference')
    order_reference = serializers.CharField(source='orderReference')
    collected_amount = serializers.IntegerField(source='collectedAmount')
    collected_currency = serializers.CharField(source='collectedCurrency')
    message = serializers.CharField()
    updated_at = serializers.DateTimeField(source='updatedAt')
    created_at = serializers.DateTimeField(source='createdAt')
    customer_name = serializers.CharField(source='customer.customerName')
    customer_phone = serializers.CharField(source='customer.customerPhoneNumber')
    customer_email = serializers.EmailField(source='customer.customerEmail', allow_blank=True)
    client_id = serializers.CharField(source='clientId')

class InitiateMobileMoneyPaymentSerializer(serializers.Serializer):
    """Serializer for initiating mobile money payments"""
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=0.01)
    currency = serializers.CharField(max_length=10, default='TZS')
    customer_name = serializers.CharField(max_length=200)
    customer_phone = serializers.CharField(max_length=20)
    customer_email = serializers.EmailField(required=False, allow_blank=True)
    mobile_provider = serializers.CharField(max_length=50)
    description = serializers.CharField(max_length=500, required=False, allow_blank=True)
    callback_url = serializers.URLField(required=False, allow_blank=True)
    
    def validate_customer_phone(self, value):
        """Validate phone number format"""
        if not re.match(r'^\+?[0-9]{9,15}$', value):
            raise serializers.ValidationError("Invalid phone number format")
        return value

class PaymentSummarySerializer(serializers.Serializer):
    """Serializer for payment summary statistics"""
    total_payments = serializers.IntegerField()
    successful_payments = serializers.IntegerField()
    pending_payments = serializers.IntegerField()
    failed_payments = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    successful_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    success_rate = serializers.FloatField()
    
class BulkPaymentStatusSerializer(serializers.Serializer):
    """Serializer for bulk payment status queries"""
    order_references = serializers.ListField(
        child=serializers.CharField(max_length=100),
        min_length=1,
        max_length=50  # Limit bulk queries
    )

class TopupRequestSerializer(serializers.Serializer):
    """Serializer for topup requests"""
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=1000)  # Minimum 1000 TZS
    phone = serializers.CharField(max_length=20)
    
    def validate_phone(self, value):
        """Validate phone number format for Tanzania"""
        # Remove any spaces or special characters
        phone = re.sub(r'[^\d+]', '', value)
        
        # Check if it's a valid Tanzanian number
        if not re.match(r'^\+?255[67]\d{8}$', phone) and not re.match(r'^0[67]\d{8}$', phone):
            raise serializers.ValidationError(
                "Invalid phone number. Please use format: +255XXXXXXXXX or 0XXXXXXXXX"
            )
        
        # Normalize to international format
        if phone.startswith('0'):
            phone = '+255' + phone[1:]
        elif not phone.startswith('+'):
            phone = '+' + phone
            
        return phone
    
    def validate_amount(self, value):
        """Validate topup amount"""
        if value < 1000:
            raise serializers.ValidationError("Minimum topup amount is 1,000 TZS")
        if value > 1000000:  # 1M TZS max
            raise serializers.ValidationError("Maximum topup amount is 1,000,000 TZS")
        return value



class TopupResponseSerializer(serializers.Serializer):
    """Serializer for topup response"""
    message = serializers.CharField()
    order_reference = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    phone = serializers.CharField()
    status = serializers.CharField()
    preview_data = serializers.DictField(required=False)





class PayoutStatusHistorySerializer(serializers.ModelSerializer):
    class Meta:
        model = PayoutStatusHistory
        fields = ['id', 'previous_status', 'new_status', 'message', 'created_at']

class PayoutSerializer(serializers.ModelSerializer):
    status_history = PayoutStatusHistorySerializer(many=True, read_only=True)
    account_number = serializers.CharField(source='account.account_number', read_only=True)
    user_email = serializers.CharField(source='account.user.email', read_only=True)
    
    class Meta:
        model = Payout
        fields = [
            'id', 'payout_reference', 'order_reference', 'clickpesa_payout_id',
            'account', 'account_number', 'user_email', 'payout_type', 'channel',
            'channel_provider', 'amount', 'currency', 'fee', 'total_amount',
            'status', 'message', 'notes', 'beneficiary_name', 'beneficiary_phone',
            'beneficiary_email', 'client_id', 'metadata', 'preview_data',
            'payout_fee_bearer', 'created_at', 'updated_at', 'clickpesa_created_at',
            'clickpesa_updated_at', 'status_history'
        ]
        read_only_fields = [
            'id', 'clickpesa_payout_id', 'fee', 'total_amount', 'status', 'message',
            'notes', 'client_id', 'created_at', 'updated_at', 'clickpesa_created_at',
            'clickpesa_updated_at', 'channel_provider', 'payout_fee_bearer'
        ]

class PayoutRequestSerializer(serializers.Serializer):
    """Serializer for payout requests"""
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=1000)  # Minimum 1000 TZS
    phone = serializers.CharField(max_length=20)
    beneficiary_name = serializers.CharField(max_length=200, required=False)
    
    def validate_phone(self, value):
        """Validate phone number format for Tanzania"""
        # Remove any spaces or special characters
        phone = re.sub(r'[^\d+]', '', value)
        
        # Check if it's a valid Tanzanian number
        if not re.match(r'^\+?255[67]\d{8}$', phone) and not re.match(r'^0[67]\d{8}$', phone):
            raise serializers.ValidationError(
                "Invalid phone number. Please use format: +255XXXXXXXXX or 0XXXXXXXXX"
            )
        
        # Normalize to international format
        if phone.startswith('0'):
            phone = '+255' + phone[1:]
        elif not phone.startswith('+'):
            phone = '+' + phone
            
        return phone
    
    def validate_amount(self, value):
        """Validate payout amount"""
        if value < 1000:
            raise serializers.ValidationError("Minimum payout amount is 1,000 TZS")
        if value > 5000000:  # 5M TZS max
            raise serializers.ValidationError("Maximum payout amount is 5,000,000 TZS")
        return value

class PayoutPreviewSerializer(serializers.Serializer):
    """Serializer for payout preview response"""
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)
    balance = serializers.DecimalField(max_digits=12, decimal_places=2)
    channel_provider = serializers.CharField(source='channelProvider')
    fee = serializers.DecimalField(max_digits=12, decimal_places=2)
    payout_fee_bearer = serializers.CharField(source='payoutFeeBearer')
    order_reference = serializers.CharField(source='order.orderReference')
    receiver_name = serializers.CharField(source='receiver.name')
    receiver_phone = serializers.CharField(source='receiver.phoneNumber')

class PayoutSummarySerializer(serializers.Serializer):
    """Serializer for payout summary statistics"""
    total_payouts = serializers.IntegerField()
    successful_payouts = serializers.IntegerField()
    pending_payouts = serializers.IntegerField()
    failed_payouts = serializers.IntegerField()
    total_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    successful_amount = serializers.DecimalField(max_digits=15, decimal_places=2)
    total_fees = serializers.DecimalField(max_digits=15, decimal_places=2)
    success_rate = serializers.FloatField()
