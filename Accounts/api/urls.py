from django.urls import path
from .views import view_account, kyc_view, dashboard, KYCOptionsView, KYCIdentityUploadView

from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    # Account endpoints
    path('accounts/', view_account, name='view_account'),
    path('dashboard/', dashboard, name='dashboard-api'),

    
    # KYC endpoints
    path('kyc/', kyc_view, name='kyc'),
    path('kyc/options/', KYCOptionsView.as_view(), name='kyc-options'),
    path('kyc/identity/upload/', KYCIdentityUploadView.as_view(), name='kyc-identity-upload'),
    
]


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)