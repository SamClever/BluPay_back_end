from django.contrib import admin
from .models import (
    Transaction, 
    Notification,
    NotificationSettings,
    VirtualCard,
    PaymentTransaction,
    NFCDevice,
    PaymentToken,
    SecuritySetting

)

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ['user', 'transaction_id', 'currency_code', 'amount', 'status', 'transaction_type','reciver', 'sender']
    list_filter = ('status', 'transaction_type', 'date')
    search_fields = ('transaction_id', 'user__username', 'description')
    readonly_fields = ('transaction_id', 'date')
    ordering = ('-date',)
    fieldsets = (
        ('General Information', {
            'fields': ('transaction_id', 'user', 'currency_code', 'amount', 'description', 'status', 'transaction_type')
        }),
        ('Sender/Receiver Details', {
            'fields': ('sender', 'reciver', 'sender_account', 'reciver_account')
        }),
        ('Timestamps', {
            'fields': ('date', 'update')
        }),
    )





@admin.register(VirtualCard)
class VirtualCardAdmin(admin.ModelAdmin):
    list_display = ('card_id', 'account', 'masked_number', 'balance', 'default_card', 'expiration_date', 'active', 'created_at')
    list_filter = ('active', 'expiration_date', 'created_at')
    search_fields = ('card_id', 'account__user__username', 'masked_number')
    ordering = ('-created_at',)
    readonly_fields = ('card_id', 'created_at')
    fieldsets = (
        ('Card Details', {
            'fields': ('card_id', 'account', 'masked_number', 'expiration_date', 'active'),
        }),
        ('Security', {
            'fields': ('card_token', 'default_card',),
        }),
        ('Metadata', {
            'fields': ('created_at',),
        }),
    )

@admin.register(PaymentTransaction)
class PaymentTransactionAdmin(admin.ModelAdmin):
    list_display = ('transaction_id', 'account', 'amount', 'txn_type', 'status', 'created_at')
    list_filter = ('status', 'txn_type', 'created_at')
    search_fields = ('transaction_id', 'account__user__username', 'description')
    ordering = ('-created_at',)
    readonly_fields = ('transaction_id', 'created_at', 'updated_at')
    fieldsets = (
        ('Transaction Info', {
            'fields': ('transaction_id', 'account', 'virtual_card', 'amount', 'txn_type', 'status', 'description'),
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
        }),
    )

@admin.register(NFCDevice)
class NFCDeviceAdmin(admin.ModelAdmin):
    list_display = ('device_id', 'account', 'device_name', 'registered_at')
    list_filter = ('registered_at',)
    search_fields = ('device_id', 'account__user__username', 'device_name')
    ordering = ('-registered_at',)
    readonly_fields = ('registered_at',)
    fieldsets = (
        ('Device Info', {
            'fields': ('account', 'device_id', 'device_name'),
        }),
        ('Metadata', {
            'fields': ('registered_at',),
        }),
    )

@admin.register(PaymentToken)
class PaymentTokenAdmin(admin.ModelAdmin):
    list_display = ('token', 'account', 'virtual_card', 'created_at', 'expires_at')
    list_filter = ('created_at', 'expires_at')
    search_fields = ('token', 'account__user__username')
    ordering = ('-created_at',)
    readonly_fields = ('token', 'created_at')
    fieldsets = (
        ('Token Info', {
            'fields': ('token', 'account', 'virtual_card'),
        }),
        ('Validity', {
            'fields': ('created_at', 'expires_at'),
        }),
    )



@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('nid', 'user', 'notification_type', 'message', 'amount', 'is_read', 'date')
    list_filter = ('notification_type', 'is_read', 'date')
    search_fields = ('nid', 'user__username', 'notification_type')
    readonly_fields = ('nid', 'date')
    ordering = ('-date',)
    fieldsets = (
        ('Notification Information', {
            'fields': ('nid', 'user', 'notification_type', 'amount', 'is_read')
        }),
        ('Timestamps', {
            'fields': ('date',)
        }),
    )


@admin.register(NotificationSettings)
class NotificationSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'general',
        'app_updates',
        'bill_reminder',
        'promotion',
        'discounts',
        'payment_request',
        'new_service',
        'new_tips',
        'updated_at',
    )
    search_fields = ('user__email', 'user__username')
    list_filter = ('general', 'app_updates', 'bill_reminder', 'promotion', 'discounts')
    readonly_fields = ('updated_at',)



@admin.register(SecuritySetting)
class SecuritySettingAdmin(admin.ModelAdmin):
    list_display = (
        'user',
        'remember_me',
        'face_id',
        'biometric_id',
        'ga_enabled',
        'updated_at',
    )
    search_fields = ('user__email', 'user__username')
    list_filter = ('face_id', 'biometric_id', 'ga_enabled')
    readonly_fields = ('updated_at',)
