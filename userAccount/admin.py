from django.contrib import admin
from userAccount.models import User
from account.models import Account, KYC

admin.site.register(User)
admin.site.register(Account)
admin.site.register(KYC)
