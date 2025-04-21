from django.urls import path
<<<<<<< HEAD
from .views import view_account, kyc_view,dashboard
=======
from .views import view_account, kyc_view, dashboard, KYCOptionsView, KYCIdentityUploadView
>>>>>>> d08e3f2 (push again)

from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    # Account endpoints
    path('accounts/', view_account, name='view_account'),
    path('dashboard/', dashboard, name='dashboard-api'),

    
    # KYC endpoints
    path('kyc/', kyc_view, name='kyc'),
<<<<<<< HEAD
=======
    path('kyc/options/', KYCOptionsView.as_view(), name='kyc-options'),
    path('kyc/identity/upload/', KYCIdentityUploadView.as_view(), name='kyc-identity-upload'),
>>>>>>> d08e3f2 (push again)
    
]


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)