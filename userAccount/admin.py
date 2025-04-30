from django.contrib import admin
from userAccount.models import User,OTPVerification,DeactivationReason
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.translation import gettext_lazy as _

# admin.site.register(User)
@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    ordering = ['email']
    list_display = ('email', 'username', 'is_active', 'is_staff', 'terms_accepted')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'terms_accepted')
    search_fields = ('email', 'username')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        (_('Personal info'), {'fields': ('username',)}),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions'),
        }),
        (_('Terms'), {'fields': ('terms_accepted',)}),
        (_('Important dates'), {'fields': ('last_login', 'date_joined')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'username', 'password1', 'password2', 'terms_accepted'),
        }),
    )

    readonly_fields = ('last_login', 'date_joined')

@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'otp_code', 'purpose', 'created_at', 'verified')
    search_fields = ('user__email', 'otp_code')
    list_filter = ('purpose', 'verified', 'created_at')



@admin.register(DeactivationReason)
class DeactivationReasonAdmin(admin.ModelAdmin):
    list_display = ('user', 'reason', 'confirmed', 'timestamp')
    list_filter = ('reason', 'confirmed', 'timestamp')
    search_fields = ('user__email', 'other_reason')
    readonly_fields = ('timestamp',)