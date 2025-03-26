from django.contrib import admin
from django.utils.html import format_html
from .models import Account, KYC

# Optional: Inline for the KYC model in the Account admin



    
class KYCInline(admin.StackedInline):
    model = KYC
    extra = 0
    readonly_fields = ('date',)
    fieldsets = (
        ('KYC Details', {
            'fields': ('full_name', 'image', 'signature', 'date_of_birth', 'gender', 'identity_type', 'identity_image')
        }),
        ('Contact & Address', {
            'fields': ('country', 'state', 'city', 'mobile', 'fax')
        }),
    )

@admin.register(Account)
class AccountAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'account_number', 'account_id', 'account_balance', 
        'account_status', 'kyc_submitted', 'kyc_confirmed', 'date'
    )
    list_filter = ('account_status', 'date')
    search_fields = ('user__username', 'account_number', 'account_id')
    ordering = ('-date',)
    readonly_fields = ('date',)
    inlines = [KYCInline]  # if you want to include KYC details inline

    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'account_balance', 'account_number', 'account_id', 'pin_number', 'red_code')
        }),
        ('Status & Verification', {
            'fields': ('account_status', 'kyc_submitted', 'kyc_confirmed')
        }),
        ('Additional Info', {
            'fields': ('recommended_by',)
        }),
        # Removed 'Metadata' fieldset containing 'date'
    )



@admin.register(KYC)
class KYCAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'gender', 'identity_type', 'country', 'state', 'city', 'date')
    list_filter = ('gender', 'identity_type', 'country', 'state')
    search_fields = ('user__username', 'full_name', 'country', 'state', 'city')
    ordering = ('-date',)
    readonly_fields = ('date',)
    fieldsets = (
        ('Personal Information', {
            'fields': ('user', 'account', 'full_name', 'image', 'signature', 'date_of_birth')
        }),
        ('Identification', {
            'fields': ('gender', 'identity_type', 'identity_image')
        }),
        ('Address & Contact', {
            'fields': ('country', 'state', 'city', 'mobile', 'fax')
        }),
        # Do not include a fieldset for 'date' since it's non-editable.
    )

    
