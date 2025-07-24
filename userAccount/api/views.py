from userAccount.models import User, OTPVerification
from userAccount.api.serializer import UserSerializer, UserRegistrationSerializer
from rest_framework.decorators import api_view
from rest_framework.response import Response
from Accounts.models import KYC
from Accounts.api.serializer import KYCSerializer
from Accounts.models import Account
from Accounts.api.serializer import AccountSerializer
from rest_framework import status
from django.contrib.auth import get_user_model
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import permission_classes
from rest_framework.request import Request
from allauth.socialaccount.models import SocialAccount, SocialToken
from django.contrib.auth.decorators import login_required
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.shortcuts import redirect
from django.shortcuts import get_object_or_404
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.contrib.auth.password_validation import validate_password
from rest_framework.exceptions import ValidationError
import requests
from django.core.mail import EmailMultiAlternatives


User = get_user_model()


"REGISTRATION  OTP SECTION"


@api_view(["POST"])
@permission_classes([AllowAny])
def register_user(request):
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        # Mark user as inactive until verified
        user.is_active = False
        user.save()
        # Create an OTP record for registration
        otp_record = OTPVerification.objects.create(user=user, purpose="registration")

        # Render email template (optional; or use a plain text message)
        # Create an email template at templates/emails/registration_otp.html
        message = render_to_string(
            "emails/registration_otp.html",
            {"user": user, "otp_code": otp_record.otp_code, "expires_in": "2 minutes"},
        )

        subject = "Your OTP Code for Registration"
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [user.email]
        email = EmailMultiAlternatives(subject, message, from_email, recipient_list)
        email.attach_alternative(message, "text/html")
        email.send()

        return Response(
            {
                "message": "User registered successfully. Please check your email for the OTP code to verify your account."
            },
            status=status.HTTP_201_CREATED,
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_registration_otp(request):
    email = request.data.get("email")
    otp_code = request.data.get("otp_code")
    if not email or not otp_code:
        return Response(
            {"error": "Email and OTP code are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)
    otp_record = user.otp_verifications.filter(
        otp_code=otp_code, purpose="registration", verified=False
    ).first()
    if otp_record:
        otp_record.verified = True
        otp_record.save()
        # Activate the user account
        user.is_active = True
        user.save()

        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        return Response(
            {"message": "Account verified successfully.", "access_token": access_token},
            status=status.HTTP_200_OK,
        )
    else:
        return Response(
            {"error": "Invalid OTP code."}, status=status.HTTP_400_BAD_REQUEST
        )


"LOGIN OTP SECTION"


@api_view(["POST"])
@permission_classes([AllowAny])
def login_request(request):
    email = request.data.get("email")
    password = request.data.get("password")
    if not email or not password:
        return Response(
            {"error": "Email and password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    user = authenticate(request, username=email, password=password)
    if user is None:
        return Response(
            {"error": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED
        )

    # Generate an OTP record for login
    otp_record = OTPVerification.objects.create(user=user, purpose="login")

    # Render an email template for login OTP
    # Render HTML email
    message = render_to_string(
        "emails/login_otp.html",
        {"user": user, "otp_code": otp_record.otp_code, "expires_in": "2 minutes"},
    )

    subject = "Your OTP Code for Login"
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]
    # Send as HTML email
    email = EmailMultiAlternatives(subject, message, from_email, recipient_list)
    email.attach_alternative(message, "text/html")
    email.send()

    return Response(
        {"message": "OTP code sent to your email. Please verify to complete login."},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_login_otp(request):
    email = request.data.get("email")
    otp_code = request.data.get("otp_code")
    if not email or not otp_code:
        return Response(
            {"error": "Email and OTP code are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    otp_record = user.otp_verifications.filter(
        otp_code=otp_code, purpose="login", verified=False
    ).first()
    if otp_record:
        otp_record.verified = True
        otp_record.save()
        # Issue JWT tokens (for example, using djangorestframework-simplejwt)
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        return Response(
            {
                "message": "Login verified successfully.",
                "access_token": access_token,
                "refresh_token": str(refresh),
            },
            status=status.HTTP_200_OK,
        )
    else:
        return Response(
            {"error": "Invalid OTP code."}, status=status.HTTP_400_BAD_REQUEST
        )


# RESEND OTP FUNCTIONALITY
@api_view(["POST"])
@permission_classes([AllowAny])
def resend_otp(request):
    """
    Resend OTP code for a given email and purpose.
    The request should include:
      - email: user's email
      - purpose: either "registration" or "login" (defaults to "registration" if not provided)
    """
    email = request.data.get("email")
    purpose = request.data.get("purpose", "registration")
    if not email:
        return Response(
            {"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST
        )
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    # Check for an existing unverified OTP for this purpose.
    otp_record = (
        user.otp_verifications.filter(purpose=purpose, verified=False)
        .order_by("-created_at")
        .first()
    )
    if not otp_record:
        otp_record = OTPVerification.objects.create(user=user, purpose=purpose)

    # Select the correct email template and subject based on the purpose.
    if purpose == "registration":
        template_name = "emails/registration_otp.html"
        subject = "Your OTP Code for Account Verification"
    elif purpose == "login":
        template_name = "emails/login_otp.html"
        subject = "Your OTP Code for Login"
    else:
        return Response(
            {"error": "Invalid OTP purpose."}, status=status.HTTP_400_BAD_REQUEST
        )

    message = render_to_string(
        template_name,
        {"user": user, "otp_code": otp_record.otp_code, "expires_in": "2 minutes"},
    )
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]
    email = EmailMultiAlternatives(subject, message, from_email, recipient_list)
    email.attach_alternative(message, "text/html")
    email.send()

    return Response(
        {"message": "OTP code has been resent to your email."},
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def forgot_password(request):
    """
    Endpoint to initiate password reset. Expects:
      { "email": "user@example.com" }
    If the email exists, an OTP (for forgot_password) is generated and sent.
    """
    email = request.data.get("email")
    if not email:
        return Response(
            {"error": "Email is required."}, status=status.HTTP_400_BAD_REQUEST
        )
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    # Create an OTP record for password reset
    otp_record = OTPVerification.objects.create(user=user, purpose="forgot_password")

    # Render an email template (create "emails/forgot_password_otp.html")
    message = render_to_string(
        "emails/forgot_password_otp.html",
        {"user": user, "otp_code": otp_record.otp_code, "expires_in": "2 minutes"},
    )
    subject = "Your OTP Code for Password Reset"
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]
    email = EmailMultiAlternatives(subject, message, from_email, recipient_list)
    email.attach_alternative(message, "text/html")
    email.send()

    return Response(
        {
            "message": "OTP code sent to your email. Please check your email to verify your identity."
        },
        status=status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([AllowAny])
def verify_forgot_password_otp(request):
    """
    Endpoint to verify the OTP for password reset.
    Expects:
      { "email": "user@example.com", "otp_code": "123456" }
    """
    email = request.data.get("email")
    otp_code = request.data.get("otp_code")
    if not email or not otp_code:
        return Response(
            {"error": "Email and OTP code are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    otp_record = (
        user.otp_verifications.filter(
            otp_code=otp_code, purpose="forgot_password", verified=False
        )
        .order_by("-created_at")
        .first()
    )

    if otp_record:
        otp_record.verified = True
        otp_record.save()
        return Response(
            {"message": "OTP verified successfully. You can now reset your password."},
            status=status.HTTP_200_OK,
        )
    else:
        return Response(
            {"error": "Invalid OTP code."}, status=status.HTTP_400_BAD_REQUEST
        )


@api_view(["POST"])
@permission_classes([AllowAny])
def reset_password(request):
    """
    Endpoint to reset the user's password.
    Expects:
      {
         "email": "user@example.com",
         "new_password": "NewSecurePassword123!",
         "confirm_password": "NewSecurePassword123!"
      }
    The endpoint checks for a verified OTP (purpose "forgot_password") before resetting the password.
    """
    email = request.data.get("email")
    new_password = request.data.get("new_password")
    confirm_password = request.data.get("confirm_password")

    if not email or not new_password or not confirm_password:
        return Response(
            {"error": "Email, new_password, and confirm_password are required."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if new_password != confirm_password:
        return Response(
            {"error": "New password and confirmation do not match."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)

    # Check that there is a verified OTP record for forgot_password
    otp_record = (
        user.otp_verifications.filter(purpose="forgot_password", verified=True)
        .order_by("-created_at")
        .first()
    )

    if not otp_record:
        return Response(
            {"error": "OTP verification required before resetting password."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Optionally, you can add a check for OTP expiration here.

    try:
        validate_password(new_password, user)
    except ValidationError as e:
        return Response({"error": e.messages}, status=status.HTTP_400_BAD_REQUEST)

    user.set_password(new_password)
    user.save()

    # Optionally, mark or delete the OTP record so it can't be reused.
    otp_record.delete()

    return Response(
        {"message": "Password reset successfully."}, status=status.HTTP_200_OK
    )


@login_required
def google_login_callback(request):
    user = request.user

    social_accounts = SocialAccount.objects.filter(user=user)
    print("social_accounts  user:", social_accounts)

    social_acccount = social_accounts.first()

    if not social_acccount:
        print("social_acccount not found")
        return redirect("http://localhost:8081/login/callback/?error=NoSocialAccount")

    token = SocialToken.objects.filter(
        account=social_acccount, account_providers="google"
    ).first()

    if token:
        print("Google token found", token.token)
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        return redirect(
            f"http://localhost:8081/login/callback/?access_token={access_token}"
        )

    else:
        print("Google token not found", user)
        return redirect("http://localhost:8081/login/callback/?error=NoGoogleToken")


@csrf_exempt
def validate_google_token(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            goog_acces_token = data["access_token"]
            print("Google token:", goog_acces_token)

            if not goog_acces_token:
                return JsonResponse(
                    {"error": "No Google access token provided"}, status=400
                )
            return JsonResponse({"message": "Google access token is valid"}, status=200)
        except json.JSONDecodeError:
            return JsonResponse({"details": "invalid json"}, status=400)
    return JsonResponse({"error": "Methods not allowed"}, status=400)


@api_view(["POST"])
@permission_classes([AllowAny])
def google_login(request):
    """
    Endpoint for logging in with a Google account.

    Expects a JSON payload:
    {
        "id_token": "<Google ID token>"
    }

    The endpoint verifies the token with Google, retrieves user details,
    creates a new user if needed, and returns JWT tokens.
    """
    id_token = request.data.get("id_token")
    if not id_token:
        return Response(
            {"error": "id_token is required."}, status=status.HTTP_400_BAD_REQUEST
        )

    # Verify the token with Google's tokeninfo endpoint.
    google_response = requests.get(
        "https://oauth2.googleapis.com/tokeninfo", params={"id_token": id_token}
    )
    if google_response.status_code != 200:
        return Response(
            {"error": "Invalid Google token."}, status=status.HTTP_400_BAD_REQUEST
        )

    token_data = google_response.json()
    email = token_data.get("email")
    email_verified = token_data.get("email_verified")

    if not email or email_verified != "true":
        return Response(
            {"error": "Google email is not verified."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    # Get or create the user.
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        # Create a new user with the email and a random password.
        user = User.objects.create_user(
            email=email,
            username=email,  # Use email as username if applicable.
            password=User.objects.make_random_password(),
        )

    # Issue JWT tokens using simplejwt.
    refresh = RefreshToken.for_user(user)
    return Response(
        {
            "message": "Login successful.",
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
        },
        status=status.HTTP_200_OK,
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def view_allUsers(request):
    user = User.objects.all()
    serializer = UserSerializer(user, many=True)
    return Response(serializer.data)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def user_id(request, pk):
    user = get_object_or_404(User, pk=pk)
    serializer = UserSerializer(user)
    return Response(serializer.data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_user(request):
    """
    Logs out the user by blacklisting their refresh token.
    Expected payload:
    {
        "refresh_token": "<your_refresh_token>"
    }
    """
    refresh_token = request.data.get("refresh_token")

    if not refresh_token:
        return Response(
            {"error": "A valid refresh token must be provided to log out."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    try:
        token = RefreshToken(refresh_token)
        token.blacklist()
        return Response(
            {"message": "You have been logged out successfully."},
            status=status.HTTP_205_RESET_CONTENT,
        )
    except TokenError:
        return Response(
            {"error": "The refresh token is invalid or has already been blacklisted."},
            status=status.HTTP_400_BAD_REQUEST,
        )
