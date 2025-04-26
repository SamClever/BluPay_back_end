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
            'fields': ('First_name', 'biometric_hash', 'date_of_birth', 'gender', 'identity_type', 'identity_image')
        }),
        ('Contact & Address', {
            'fields': ('country', 'state', 'city', 'mobile')
        }),
        ('Verification Images', {
            'fields': ('profile_image', 'selfie_image')
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
            'fields': ('recommended_by', 'fingerprint_enabled', 'fingerprint_secret','faceid_enabled', 'faceid_secret')
        }),
        # Removed 'Metadata' fieldset containing 'date'
    )



@admin.register(KYC)
class KYCAdmin(admin.ModelAdmin):
    list_display = ('user', 'First_name','Last_name', 'gender', 'identity_type', 'country', 'state', 'city', 'date')
    list_filter = ('gender', 'identity_type', 'country', 'state')
    search_fields = ('user__username', 'First_name', 'country', 'state', 'city')
    ordering = ('-date',)
    readonly_fields = ('date',)
    fieldsets = (
        ('Personal Information', {
            'fields': ('user', 'account', 'First_name','Last_name', 'profile_image', 'biometric_hash', 'date_of_birth')
        }),
        ('Identification', {
            'fields': ('gender', 'identity_type', 'identity_image', 'selfie_image')
        }),
        ('Address & Contact', {
            'fields': ('country', 'state', 'city', 'mobile', 'address_line1', 'address_line2', 'zip_code')
        }),
    )
