
from userAccount.models import User,OTPVerification
from userAccount.api.serializer import UserSerializer,UserRegistrationSerializer
from rest_framework.decorators import api_view
from rest_framework.response import Response
from Accounts.models import KYC
from Accounts.api.serializer import KycSerializer
from Accounts.models import Account
from Accounts.api.serializer import AccountSerializer
from rest_framework import status
from django.contrib.auth import get_user_model
from rest_framework.permissions import AllowAny
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import permission_classes
from rest_framework.request import Request
from allauth.socialaccount.models import SocialAccount,SocialToken
from django.contrib.auth.decorators import login_required
from rest_framework_simplejwt.tokens import RefreshToken
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json
from django.shortcuts import redirect
from django.shortcuts import get_object_or_404
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string




User = get_user_model()



"REGISTRATION  OTP SECTION" 
@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        # Mark user as inactive until verified
        user.is_active = False
        user.save()
        # Create an OTP record for registration
        otp_record = OTPVerification.objects.create(user=user, purpose='registration')
        
        # Render email template (optional; or use a plain text message)
        # Create an email template at templates/emails/registration_otp.html
        message = render_to_string('emails/registration_otp.html', {
            'user': user,
            'otp_code': otp_record.otp_code,
        })
        subject = 'Your OTP Code for Account Verification'
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [user.email]
        send_mail(subject, message, from_email, recipient_list)
        
        return Response(
            {"message": "User registered successfully. Please check your email for the OTP code to verify your account."},
            status=status.HTTP_201_CREATED
        )
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@api_view(['POST'])
@permission_classes([AllowAny])
def verify_registration_otp(request):
    email = request.data.get('email')
    otp_code = request.data.get('otp_code')
    if not email or not otp_code:
        return Response({"error": "Email and OTP code are required."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)
    otp_record = user.otp_verifications.filter(otp_code=otp_code, purpose='registration', verified=False).first()
    if otp_record:
        otp_record.verified = True
        otp_record.save()
        # Activate the user account
        user.is_active = True
        user.save()
        return Response({"message": "Account verified successfully."}, status=status.HTTP_200_OK)
    else:
        return Response({"error": "Invalid OTP code."}, status=status.HTTP_400_BAD_REQUEST)



"LOGIN OTP SECTION" 
@api_view(['POST'])
@permission_classes([AllowAny])
def login_request(request):
    email = request.data.get('email')
    password = request.data.get('password')
    if not email or not password:
        return Response({"error": "Email and password are required."}, status=status.HTTP_400_BAD_REQUEST)
    
    user = authenticate(request, username=email, password=password)
    if user is None:
        return Response({"error": "Invalid credentials."}, status=status.HTTP_401_UNAUTHORIZED)
    
    # Generate an OTP record for login
    otp_record = OTPVerification.objects.create(user=user, purpose='login')
    
    # Render an email template for login OTP
    message = render_to_string('emails/login_otp.html', {
        'user': user,
        'otp_code': otp_record.otp_code,
    })
    subject = 'Your OTP Code for Login'
    from_email = settings.DEFAULT_FROM_EMAIL
    recipient_list = [user.email]
    send_mail(subject, message, from_email, recipient_list)
    
    return Response({"message": "OTP code sent to your email. Please verify to complete login."}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([AllowAny])
def verify_login_otp(request):
    email = request.data.get('email')
    otp_code = request.data.get('otp_code')
    if not email or not otp_code:
        return Response({"error": "Email and OTP code are required."}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        user = User.objects.get(email=email)
    except User.DoesNotExist:
        return Response({"error": "User not found."}, status=status.HTTP_404_NOT_FOUND)
    
    otp_record = user.otp_verifications.filter(otp_code=otp_code, purpose='login', verified=False).first()
    if otp_record:
        otp_record.verified = True
        otp_record.save()
        # Issue JWT tokens (for example, using djangorestframework-simplejwt)
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        return Response({"message": "Login verified successfully.", "access_token": access_token}, status=status.HTTP_200_OK)
    else:
        return Response({"error": "Invalid OTP code."}, status=status.HTTP_400_BAD_REQUEST)
    

    




@login_required
def google_login_callback(request):
    user = request.user

    social_accounts =  SocialAccount.objects.filter(user=user)
    print("social_accounts  user:",social_accounts)

    social_acccount = social_accounts.first()

    if not social_acccount:
        print("social_acccount not found")
        return redirect("http://localhost:8081/login/callback/?error=NoSocialAccount")
    
    token = SocialToken.objects.filter(account=social_acccount, account_providers='google').first()

    if token:
        print("Google token found", token.token)
        refresh = RefreshToken.for_user(user)
        access_token = str(refresh.access_token)
        return redirect(f"http://localhost:8081/login/callback/?access_token={access_token}")
    
    else:
        print("Google token not found", user)
        return redirect("http://localhost:8081/login/callback/?error=NoGoogleToken")


@csrf_exempt
def validate_google_token(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            goog_acces_token = data['access_token']
            print("Google token:", goog_acces_token)

            if not goog_acces_token:
                return JsonResponse({'error': 'No Google access token provided'}, status=400)
            return JsonResponse({'message': 'Google access token is valid'}, status=200)
        except json.JSONDecodeError:
            return JsonResponse({'details':'invalid json'}, status=400)
    return JsonResponse({'error': 'Methods not allowed'}, status=400)





@api_view(['GET'])
@permission_classes([AllowAny])
def view_allUsers(request):
    user = User.objects.all()
    serializer = UserSerializer(user, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_id(request, pk):
    user = get_object_or_404(User, pk=pk)
    serializer = UserSerializer(user)
    return Response(serializer.data)