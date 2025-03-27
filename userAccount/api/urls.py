from django.urls import path
from .views import (
    view_allUsers,
    user_id,
    register_user,
    google_login_callback,
    validate_google_token,
    verify_registration_otp,
    login_request,
    verify_login_otp,
    resend_otp,
    forgot_password, 
    verify_forgot_password_otp, 
    reset_password
)
from django.conf import settings
from django.conf.urls.static import static
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView



urlpatterns = [
    #REGISTRATIO COMPLETE
    path('register/', register_user, name='register_user'),
    path('verify-registration-otp/', verify_registration_otp, name='verify_registration_otp'),
    path('login/', login_request, name='login_request'),
    path('verify-login-otp/', verify_login_otp, name='verify_login_otp'),
    path('resend-otp/', resend_otp, name='resend_otp'),
    path('forgot-password/', forgot_password, name='forgot_password'),
    path('verify-forgot-password-otp/', verify_forgot_password_otp, name='verify_forgot_password_otp'),
    path('reset-password/', reset_password, name='reset_password'),
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('callback/', google_login_callback, name='callback'),
    path('api/google/validate/', validate_google_token, name='validate_token'),


    path('', view_allUsers, name='view_allUsers'),  # Matches: /movies/
    path('<int:pk>/', user_id, name='user_id'),  # Matches: /movies/1/
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)