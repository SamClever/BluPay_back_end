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
    inlines = [KYCInline]  # Shows KYC details inline if available

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
        ('Metadata', {
            'fields': ('date',)
        }),
    )

    def get_fieldsets(self, request, obj=None):
        # When adding a new Account (obj is None), remove the Metadata fieldset
        if obj is None:
            fieldsets = super().get_fieldsets(request, obj)
            # Exclude any fieldset that contains 'date'
            fieldsets = tuple(
                (name, opts)
                for name, opts in fieldsets
                if 'date' not in opts.get('fields', ())
            )
            return fieldsets
        return super().get_fieldsets(request, obj)



@admin.register(KYC)
class KYCAdmin(admin.ModelAdmin):
    list_display = ('user', 'full_name', 'gender', 'identity_type', 'country', 'state', 'city', 'date')
    list_filter = ('gender', 'identity_type', 'country', 'state')
    search_fields = ('user__username', 'full_name', 'country', 'state', 'city')
    ordering = ('-date',)

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
        ('Metadata', {
            'fields': ('date',)
        }),
    )
