from django.urls import path
from .views import (
    view_account,
      kyc_view, 
      dashboard,
      kyc_step1,
      kyc_step2_view
      ,kyc_step3_view,
      kyc_step4_view,
      kyc_step5_view,
      kyc_activate_view,
      set_pin,
      change_pin,
      reset_pin,
      verify_pin,
      enable_fingerprint,
      fingerprint_login,
      enable_faceid,
      faceid_login,
      account_summary,
      update_account_limits
)

from django.conf import settings
from django.conf.urls.static import static
urlpatterns = [
    # Account endpoints
    path('accounts/', view_account, name='view_account'),
    path('accounts/summary/', account_summary, name='account_summary'),
    path('accounts/update-limits/', update_account_limits, name='update_account_limits'),
    path('account/set-pin/', set_pin, name='account-set-pin'),
    path('account/change-pin/', change_pin, name='change-pin'),
    path('account/reset-pin/', reset_pin, name='reset-pin'),
    path('account/verify-pin/', verify_pin, name='verify-pin'),
    path('account/enable-fingerprint/', enable_fingerprint, name='enable-fingerprint'),
    path('auth/fingerprint-login/',     fingerprint_login,   name='fingerprint-login'),
    path('account/enable-faceid/', enable_faceid, name='enable-faceid'),
    path('auth/faceid-login/',      faceid_login,   name='faceid-login'),


    # KYC endpoints
    path('kyc/', kyc_view, name='kyc'),
    path('kyc/step1/', kyc_step1, name='api-kyc-step1'),
    path('kyc/step2/', kyc_step2_view, name='api-kyc-step2'),
    path('kyc/step3/', kyc_step3_view, name='kyc-step3'),
    path('kyc/step4/', kyc_step4_view, name='kyc-step4'),
    path('kyc/step5/', kyc_step5_view,  name='kyc-step5'),
    path('kyc/activate/', kyc_activate_view, name='kyc-activate'),

    # Home dashboad
    path('dashboard/', dashboard, name='dashboard-api'),
    
]


if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)