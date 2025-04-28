from rest_framework import serializers
from .utils import validate_card_number, mask_card_number, detect_card_type, validate_expiration_date
from django.db.models import Q
from decimal import Decimal
from django.utils.translation import get_language
from Accounts.models import * 
import babel
from babel.numbers import format_currency

from bluepay.models import (
    Transaction, 
    Notification ,
    VirtualCard,
    PaymentTransaction,
    NFCDevice,
    PaymentToken,
    CURRENCY_CHOICES
)

class TransactionSerializer(serializers.ModelSerializer):
    sender_name       = serializers.SerializerMethodField()
    recipient_name    = serializers.SerializerMethodField()
    currency_code     = serializers.CharField(source='currency_code')
    formatted_amount  = serializers.SerializerMethodField()
    date              = serializers.DateTimeField(format="%Y-%m-%d %H:%M:%S")

    
    class Meta:
        model = Transaction
        fields = [
            'transaction_id',
            'amount',
            'formatted_amount',
            'currency_code',
            'description',
            'status',
            'transaction_type',
            'sender_name',
            'recipient_name',
            'date',
        ]

    def get_sender_name(self, tx):
        u = tx.sender
        return u.get_full_name() or u.email

    def get_recipient_name(self, tx):
        u = tx.reciver
        return u.get_full_name() or u.email

    def get_formatted_amount(self, tx):
        # e.g. "$1,234.56" or "TZS 1,234.56"
        return format_currency(tx.amount, tx.currency_code, locale=get_language())



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
    currency_code  = serializers.ChoiceField(choices=CURRENCY_CHOICES, default='TZS')
    description    = serializers.CharField(allow_blank=True, required=False)

    

    def validate_account_number(self, value):
        # load the target Account
        try:
            acct = Account.objects.get(
                Q(account_number=value) | Q(account_id=value)
            )
        except Account.DoesNotExist:
            raise serializers.ValidationError("That account does not exist.")

        # must be fully KYC-confirmed & active
        if not acct.kyc_confirmed:
            raise serializers.ValidationError("Recipient’s account is not KYC-confirmed.")
        if acct.account_status != "active":
            raise serializers.ValidationError("Recipient’s account is not active.")
        return acct

    def validate(self, attrs):
        sender_ac = self.context['request'].user.account
        recipient_ac = attrs['account_number']
        amt = attrs['amount']

        # sender must also be KYC-confirmed & active
        if not sender_ac.kyc_confirmed:
            raise serializers.ValidationError("You must complete KYC before transferring.")
        if sender_ac.account_status != "active":
            raise serializers.ValidationError("Your account is not active.")

        # no self-transfer
        if recipient_ac == sender_ac:
            raise serializers.ValidationError("Cannot transfer to your own account.")

        # sufficient balance
        if sender_ac.account_balance < amt:
            raise serializers.ValidationError("Insufficient funds.")

        attrs['recipient_account'] = recipient_ac
        return attrs

   

    def create(self, validated_data):
        user = self.context['request'].user
        tx = Transaction.objects.create(
            user=user,
            amount=validated_data['amount'],
            currency_code    = validated_data['currency_code'],   # ← store it
            description=validated_data.get('description', ''),
            sender=user,
            reciver=validated_data['recipient_account'].user,
            sender_account=user.account,
            reciver_account=validated_data['recipient_account'],
            transaction_type="transfer",
            status="processing",
        )
        return tx


SYMBOLS = {'TZS': 'TSh', 'USD':'$'}


class TransactionSerializer(serializers.ModelSerializer):
    sender_account_number   = serializers.CharField(source='sender_account.account_number', read_only=True)
    reciver_account_number  = serializers.CharField(source='reciver_account.account_number', read_only=True)

    sender_name             = serializers.SerializerMethodField()
    sender_profile_image    = serializers.SerializerMethodField()

    receiver_name           = serializers.SerializerMethodField()
    receiver_profile_image  = serializers.SerializerMethodField()
    
    date                   = serializers.DateTimeField(
                                format="%b %d, %Y | %I:%M:%S %p",
                                read_only=True
                            )
  


    currency_code    = serializers.CharField(read_only=True)
    formatted_amount = serializers.SerializerMethodField()

    
    class Meta:
        model  = Transaction
        fields = [
            'transaction_id',
            'amount',
            'currency_code',
            'formatted_amount',
            'description',
            'status',
            'sender_name',
            'sender_profile_image',
            'receiver_name',
            'receiver_profile_image',
            'sender_account_number',
            'reciver_account_number',
            'date',
        ]

    def get_sender_name(self, obj):
        k = getattr(obj.sender, 'kyc', None)
        if k:
            return f"{k.First_name} {k.Last_name or ''}".strip()
        return obj.sender.email

    def get_receiver_name(self, obj):
        k = getattr(obj.reciver, 'kyc', None)
        if k:
            return f"{k.First_name} {k.Last_name or ''}".strip()
        return obj.reciver.email

    def _build_image_url(self, image_field):
        if not image_field:
            return None
        request = self.context.get('request')
        return request.build_absolute_uri(image_field.url)

    def get_sender_profile_image(self, obj):
        k = getattr(obj.sender, 'kyc', None)
        return self._build_image_url(k.profile_image) if k else None

    def get_receiver_profile_image(self, obj):
        k = getattr(obj.reciver, 'kyc', None)
        return self._build_image_url(k.profile_image) if k else None

    def get_formatted_amount(self, obj):
        locale = self.context.get('locale', 'en_US')
        try:
            return babel.numbers.format_currency(
                obj.amount, obj.currency_code, locale=locale
            )
        except:
            return f"{obj.amount} {obj.currency_code}"

    def get_receiver_profile_photo(self, obj):
        photo = getattr(obj.reciver.kyc, 'profile_photo', None)
        if photo and hasattr(photo, 'url'):
            request = self.context.get('request')
            return request.build_absolute_uri(photo.url)
        return None
    

    

    # def get_formatted_amount(self, tx):
    #     sym = SYMBOLS.get(tx.currency_code, tx.currency_code+' ')
    #     # comma thousands, two decimal places
    #     return f"{sym} {tx.amount:,.2f}"


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
    




class InitiateRequestSerializer(serializers.Serializer):
    account_number = serializers.CharField()
    amount         = serializers.DecimalField(max_digits=12, decimal_places=2)
    description    = serializers.CharField(required=False, allow_blank=True)

    def validate_account_number(self, value):
        # look up the recipient account
        try:
            acct = Account.objects.get(
                Q(account_number=value) | Q(account_id=value)
            )
        except Account.DoesNotExist:
            raise serializers.ValidationError("That account does not exist.")
        if not acct.kyc_confirmed:
            raise serializers.ValidationError("Recipient’s account is not KYC-confirmed.")
        if acct.account_status != "active":
            raise serializers.ValidationError("Recipient’s account is not active.")
        return acct

    def validate(self, attrs):
        sender_ac = self.context['request'].user.account
        recipient_ac = attrs['account_number']
        # sender must be KYC-confirmed & active
        if not sender_ac.kyc_confirmed:
            raise serializers.ValidationError("You must complete KYC before requesting payment.")
        if sender_ac.account_status != "active":
            raise serializers.ValidationError("Your account is not active.")
        # no self-request
        if recipient_ac == sender_ac:
            raise serializers.ValidationError("Cannot request payment from yourself.")
        return attrs

    def create(self, validated_data):
        user = self.context['request'].user
        recipient_acct = validated_data['account_number']
        tx = Transaction.objects.create(
            user=user,
            amount=validated_data['amount'],
            currency_code=user.account.country_currency_code,  # or however you derive default
            description=validated_data.get('description', ''),
            sender=user,
            reciver=recipient_acct.user,
            sender_account=user.account,
            reciver_account=recipient_acct,
            transaction_type="request",
            status="processing",
        )
        return tx