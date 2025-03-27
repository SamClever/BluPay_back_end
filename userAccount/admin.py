from django.contrib import admin
from userAccount.models import User,OTPVerification

admin.site.register(User)

@admin.register(OTPVerification)
class OTPVerificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'otp_code', 'purpose', 'created_at', 'verified')
    search_fields = ('user__email', 'otp_code')
    list_filter = ('purpose', 'verified', 'created_at')