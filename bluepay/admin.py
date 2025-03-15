from django.contrib import admin
from .models import Transaction, CreditCard, Notification

@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'transaction_id', 'user', 'amount', 'status', 'transaction_type', 'date'
    )
    list_filter = ('status', 'transaction_type', 'date')
    search_fields = ('transaction_id', 'user__username', 'description')
    readonly_fields = ('transaction_id', 'date')
    ordering = ('-date',)
    fieldsets = (
        ('General Information', {
            'fields': ('transaction_id', 'user', 'amount', 'description', 'status', 'transaction_type')
        }),
        ('Sender/Receiver Details', {
            'fields': ('sender', 'reciver', 'sender_account', 'reciver_account')
        }),
        ('Timestamps', {
            'fields': ('date', 'update')
        }),
    )


@admin.register(CreditCard)
class CreditCardAdmin(admin.ModelAdmin):
    list_display = (
        'card_id', 'user', 'name', 'number', 'card_type', 'card_status', 'amount', 'date'
    )
    list_filter = ('card_type', 'card_status', 'date')
    search_fields = ('card_id', 'user__username', 'name', 'number')
    readonly_fields = ('card_id', 'date')
    ordering = ('-date',)
    fieldsets = (
        ('Card Details', {
            'fields': ('card_id', 'user', 'name', 'number', 'month', 'year', 'cvv', 'card_type')
        }),
        ('Financial Information', {
            'fields': ('amount', 'card_status')
        }),
        ('Timestamps', {
            'fields': ('date',)
        }),
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('nid', 'user', 'notification_type', 'amount', 'is_read', 'date')
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
