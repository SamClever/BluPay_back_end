
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('userAuth/', include('userAccount.api.urls')), 
    path('Account/', include('account.api.urls')), 
    
]
