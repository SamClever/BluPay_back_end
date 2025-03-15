from django.urls import path
from .views import view_account, view_account_id, view_kyc, view_kyc_id

from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    # Account endpoints
    path('accounts/', view_account, name='view_account'),
    path('accounts/<uuid:pk>/', view_account_id, name='view_account_id'),
    
    # KYC endpoints
    path('kyc/', view_kyc, name='view_kyc'),
    path('kyc/<uuid:pk>/', view_kyc_id, name='view_kyc_id'),
    
]


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)