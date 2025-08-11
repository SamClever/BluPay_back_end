from django.shortcuts import get_object_or_404
from userAccount.models import User
from userAccount.api.serializer import UserSerializer
from Accounts.api.serializer import *
from Accounts.models import Account, KYC
from rest_framework.decorators import api_view,permission_classes,parser_classes
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated,AllowAny
from django.core.mail import send_mail, EmailMultiAlternatives
from django.conf import settings
from django.template.loader import render_to_string
from rest_framework import generics  # Import generics from rest_framework
from rest_framework.views import APIView  # Import APIView
from django_countries import countries
from Accounts.models import IDENTITY_TYPE
from rest_framework_simplejwt.tokens import RefreshToken
import pycountry  # Removed as it is not accessed
from .utils                        import compare_faces_aws
import uuid
from django.conf import settings
from decimal import Decimal
from bluepay.models import *
from bluepay.api.serializers import *

from bluepay.api.utils import *
import logging
logger = logging.getLogger(__name__)
from bluepay.models import  Payment, PaymentStatusHistory, MobileMoneyProvider, Transaction

# -----------------------------------------------------------------------------
# Account API Endpoint
# -----------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def view_account(request):
    user = request.user
    try:
        kyc = KYC.objects.get(user=user)
    except KYC.DoesNotExist:
        return Response(
            {"detail": "You need to submit your KYC first."},
            status=status.HTTP_404_NOT_FOUND
        )
        
    account = get_object_or_404(Account, user=user)
    account_serializer = AccountSerializer(account)
    kyc_serializer = KYCSerializer(kyc, context={'request': request})
    return Response({
        "account": account_serializer.data,
        "kyc": kyc_serializer.data,
    }, status=status.HTTP_200_OK)




# -----------------------------------------------------------------------------
# KYC Registration API Endpoint
# -----------------------------------------------------------------------------

@api_view(['GET', 'POST', 'PATCH'])
@permission_classes([IsAuthenticated])
def kyc_view(request):
    """
    GET: Retrieve the current KYC data.
    POST: Create a new KYC record using the provided data.
    PATCH: Update an existing KYC record.
    
    After a successful create/update, mark account.kyc_submitted = True and send account details by email.
    """
    user = request.user
    account = get_object_or_404(Account, user=user)
    
    # Try to get the user's existing KYC record.
    try:
        kyc_record = user.kyc  # Using the reverse one-to-one relationship.
    except KYC.DoesNotExist:
        kyc_record = None

    # --- GET: Return KYC record if available ---
    if request.method == 'GET':
        if kyc_record is None:
            return Response({"error": "KYC record not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = KYCSerializer(kyc_record, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    # --- POST: Create a new KYC record ---
    if request.method == 'POST':
        if kyc_record is not None:
            return Response({"error": "KYC record already exists."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = KYCSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            kyc_record = serializer.save(user=user, account=account)
            # Mark account as having submitted KYC.
            account.kyc_submitted = True
            account.save()
            
            # Prepare and send email with account details.
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [user.email]
            subject = "Your Account - KYC Submission Received"
            html_message = render_to_string('emails/account_details.html', {
                'user': user,
                'account_number': account.account_number,
                'pin_number': account.pin_number,
            })
            send_mail(subject, "", from_email, recipient_list, html_message=html_message)
            
            return Response({
                "message": ("KYC submitted successfully. Please check your email for your account details. "
                            "Payment functionality is paused until your KYC is verified."),
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # --- PATCH: Update the existing KYC record ---
    if request.method == 'PATCH':
        if kyc_record is None:
            return Response({"error": "KYC record not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = KYCSerializer(kyc_record, data=request.data, partial=True, context={'request': request})
        if serializer.is_valid():
            serializer.save()
            account.kyc_submitted = True
            account.save()
            return Response({
                "message": "KYC updated successfully.",
                "data": serializer.data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



# -----------------------------------------------------------------------------
# KYCOPTIONS VIEW API Endpoint
# -----------------------------------------------------------------------------
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def kyc_step1(request):
    """
    Screen 1 of KYC: choose identity type & country.
    """
    if request.method == 'GET':
        identity_choices = [
            {'key': key, 'label': label}
            for key, label in IDENTITY_TYPE
        ]
        countries = [
            {'code': c.alpha_2, 'name': c.name}
            for c in pycountry.countries
        ]
        return Response({
            'identity_types': identity_choices,
            'countries': countries
        })

    # POST: user has chosen their type & country
    serializer = KYCStep1Serializer(
        data=request.data,
        context={'request': request}
    )
    # raise a 400 with a JSON body if invalid
    serializer.is_valid(raise_exception=True)

    # this calls your ⁠ create() ⁠ above
    kyc = serializer.save()

    return Response({
        'message': 'Thank you for choosing your identity type & country',
        'kyc': {
            'identity_type': kyc.identity_type,
            'country':       kyc.country,
        }
    }, status=status.HTTP_200_OK)
    





# -----------------------------------------------------------------------------
# KYC IDENTITY VIEW API Endpoint
# -----------------------------------------------------------------------------
@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def kyc_step2_view(request):
    """
    GET:  return current image URL (or null)
    POST: accept a multipart‐form file under key `identity_image`
    """
    kyc = get_object_or_404(KYC, user=request.user)

    if request.method == 'GET':
        data = {
            'identity_image_url': (
                request.build_absolute_uri(kyc.identity_image.url)
                if kyc.identity_image
                else None
            )
        }
        return Response(data)

    # POST
    # ensure the client actually sent a file
    if 'identity_image' not in request.FILES:
        return Response(
            {'error': 'No file provided under "identity_image".'},
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = KYCStep2Serializer(kyc, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # save will store the file to MEDIA_ROOT and update kyc.identity_image
    serializer.save()

    # now safe to build the URL
    url = request.build_absolute_uri(serializer.instance.identity_image.url)
    return Response(
        {
            'message': 'ID-card image uploaded successfully.',
            'identity_image_url': url
        },
        status=status.HTTP_200_OK
    )






@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def kyc_step3_view(request):
    """
    GET:  see your selfie URL + verification result
    POST: upload `selfie_image`; runs face match & returns score
    """
    kyc = get_object_or_404(KYC, user=request.user)

    if request.method == 'GET':
        return Response({
            'selfie_image_url': (
                request.build_absolute_uri(kyc.selfie_image.url)
                if kyc.selfie_image else None
            ),
            'face_verified':    kyc.face_verified,
            'face_match_score': kyc.face_match_score,
        })

    # POST
    if 'selfie_image' not in request.FILES:
        return Response(
            {'error': 'Please attach a file under "selfie_image".'},
            status=status.HTTP_400_BAD_REQUEST
        )

    serializer = KYCStep3Serializer(kyc, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # save selfie to disk first
    serializer.save()

    # now compare with ID
    if not kyc.identity_image:
        return Response(
            {'error': 'No ID image on file. Complete step 2 first.'},
            status=status.HTTP_400_BAD_REQUEST
        )

    match, score = compare_faces_aws(
        kyc.identity_image.path,
        kyc.selfie_image.path
    )
    kyc.face_verified    = match
    kyc.face_match_score = score
    kyc.save()

    return Response({
        'message':          'Face verification complete.',
        'face_verified':    match,
        'face_match_score': score
    }, status=status.HTTP_200_OK)





@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser, FormParser, MultiPartParser])
def kyc_step4_view(request):
    """
    Step 4: Submit personal info + phone
    """
    kyc = get_object_or_404(KYC, user=request.user)
    serializer = KYCStep4Serializer(kyc, data=request.data, partial=True)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    serializer.save()
    return Response({
        'message': 'Personal info submitted.',
        'data':    serializer.data
    }, status=status.HTTP_200_OK)




@api_view(['GET'])
@permission_classes([IsAuthenticated])
def kyc_step5_view(request):
    """
    Step 5 KYC: return a “review” of everything the user has filled so far.
    """
    acct = get_object_or_404(Account, user=request.user)

    # Don't require account match immediately
    kyc = KYC.objects.filter(user=request.user).first()

    
    if not acct.kyc_submitted:
        acct.kyc_submitted = True
        acct.account_status = 'pending'
        acct.save()

    data = KYCStep5Serializer(kyc, context={'request': request}).data
    # also include flags so the client knows where they are:
    data.update({
        'account_number': acct.account_number,
        'kyc_submitted': acct.kyc_submitted,
        'kyc_confirmed': acct.kyc_confirmed,
        'account_status': acct.account_status,
    })
    return Response(data, status=status.HTTP_200_OK)





@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def set_pin(request):
    """
    Step 6: user chooses a 4-digit PIN. We save it, keep account pending,
    and send them an email with their account number+PIN.
    """
    ser = SetPinSerializer(data=request.data)
    ser.is_valid(raise_exception=True)

    acct = get_object_or_404(Account, user=request.user)

    # must have already submitted KYC
    if not acct.kyc_submitted:
        return Response(
            {"detail": "You must finish KYC before setting PIN."},
            status=status.HTTP_400_BAD_REQUEST
        )
    # can't re-set once confirmed
    if acct.kyc_confirmed:
        return Response(
            {"detail": "Account already verified — PIN cannot be changed."},
            status=status.HTTP_400_BAD_REQUEST
        )
    

    # save the new PIN
    acct.pin_number     = ser.validated_data['pin']
    acct.account_status = 'pending'
    acct.save()

    # send email
    subject = "Your Blupay account number & PIN"
    body    = render_to_string("emails/account_details.html", {
        "user":           request.user,
        "account_number": acct.account_number,
        "pin":            acct.pin_number,
    })
    send_mail(
        subject,
        body,
        settings.DEFAULT_FROM_EMAIL,
        [request.user.email],
        html_message=body,
    )

    return Response({
        "message":         "PIN created sucessfully. Check your email for account details.",
        "account_number":  acct.account_number,
        "kyc_submitted":   acct.kyc_submitted,
        "kyc_confirmed":   acct.kyc_confirmed,
        "account_status":  acct.account_status,
    }, status=status.HTTP_200_OK)






@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def change_pin(request):
    """
    Change account PIN - requires current PIN for verification
    """
    serializer = ChangePinSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    account = get_object_or_404(Account, user=request.user)
    
    # Check if account has a PIN set
    if not account.pin_number:
        return Response(
            {"detail": "No PIN is currently set. Please set a PIN first."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Verify current PIN
    current_pin = serializer.validated_data['current_pin']
    if account.pin_number != current_pin:
        logger.warning(f"Invalid PIN change attempt for user {request.user.email}")
        return Response(
            {"detail": "Current PIN is incorrect."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Check if account is active
    if account.account_status not in ['active', 'pending']:
        return Response(
            {"detail": "Account must be active to change PIN."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # New PIN
    new_pin = serializer.validated_data['new_pin']

    # ✅ Ensure new PIN is unique
    if Account.objects.filter(pin_number=new_pin).exclude(pk=account.pk).exists():
        return Response(
            {"detail": "This PIN is already in use by another account."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    old_pin = account.pin_number
    account.pin_number = new_pin
    account.save()
    
    # Send confirmation email
    try:
        subject = "BluPay PIN Changed Successfully"
        html_body = render_to_string("emails/pin_changed.html", {
            "user": request.user,
            "account_number": account.account_number,
            "change_date": timezone.now().strftime("%Y-%m-%d %H:%M"),
            "old_pin_masked": f"***{old_pin[-1]}",
            "new_pin_masked": f"***{new_pin[-1]}",
        })
        
        email = EmailMultiAlternatives(
            subject=subject,
            body="Your BluPay PIN has been changed successfully.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[request.user.email],
        )
        email.attach_alternative(html_body, "text/html")
        email.send(fail_silently=True)
        
        logger.info(f"PIN changed successfully for user {request.user.email}")
    except Exception as e:
        logger.error(f"Failed to send PIN change email to {request.user.email}: {e}")
    
    return Response({
        "message": "PIN changed successfully. A confirmation email has been sent.",
        "account_number": account.account_number,
        "changed_at": timezone.now().isoformat(),
    }, status=status.HTTP_200_OK)
    

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def reset_pin(request):
    """
    Reset PIN using security questions or admin approval
    This is for users who forgot their PIN
    """
    account = get_object_or_404(Account, user=request.user)
    
    # Check if KYC is confirmed (security requirement)
    if not account.kyc_confirmed:
        return Response(
            {"detail": "KYC verification required for PIN reset."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # For now, we'll require admin approval for PIN reset
    # In a production system, you might implement security questions
    
    # Generate a temporary reset token (you could store this in the database)
    reset_token = uuid.uuid4().hex[:8].upper()
    
    # Send email to user with reset instructions
    try:
        subject = "BluPay PIN Reset Request"
        html_body = render_to_string("emails/pin_reset_request.html", {
            "user": request.user,
            "account_number": account.account_number,
            "reset_token": reset_token,
            "request_date": timezone.now().strftime("%Y-%m-%d %H:%M"),
        })
        
        email = EmailMultiAlternatives(
            subject=subject,
            body="PIN reset request received. Please contact support.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[request.user.email],
        )
        email.attach_alternative(html_body, "text/html")
        email.send(fail_silently=True)
        
        # Also send notification to admin/support
        admin_email = getattr(settings, 'ADMIN_EMAIL', 'info@theblupay.com')
        admin_subject = f"PIN Reset Request - {account.account_number}"
        admin_body = f"""
        PIN reset request received:
        
        User: {request.user.email}
        Account: {account.account_number}
        Reset Token: {reset_token}
        Request Time: {timezone.now()}
        
        Please verify the user's identity before approving the reset.
        """
        
        send_mail(
            admin_subject,
            admin_body,
            settings.DEFAULT_FROM_EMAIL,
            [admin_email],
            fail_silently=True
        )
        
        logger.info(f"PIN reset requested for user {request.user.email}")
    except Exception as e:
        logger.error(f"Failed to send PIN reset email to {request.user.email}: {e}")
    
    return Response({
        "message": "PIN reset request submitted. Please check your email for further instructions.",
        "reset_token": reset_token,
        "status": "pending_approval"
    }, status=status.HTTP_200_OK)

@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def verify_pin(request):
    """
    Verify PIN without changing it - useful for sensitive operations
    """
    pin = request.data.get('pin')
    if not pin:
        return Response(
            {"detail": "PIN is required."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    if len(pin) != 4 or not pin.isdigit():
        return Response(
            {"detail": "PIN must be 4 digits."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    account = get_object_or_404(Account, user=request.user)
    
    if not account.pin_number:
        return Response(
            {"detail": "No PIN is set for this account."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    is_valid = account.pin_number == pin
    
    if not is_valid:
        logger.warning(f"Invalid PIN verification attempt for user {request.user.email}")
    
    return Response({
        "valid": is_valid,
        "message": "PIN verified successfully" if is_valid else "Invalid PIN"
    }, status=status.HTTP_200_OK if is_valid else status.HTTP_400_BAD_REQUEST)



# -----------------------------------------------------------------------------
# ENABLE API Endpoint
# -----------------------------------------------------------------------------
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def enable_fingerprint(request):
    """
    Step 7a: Register this device for fingerprint login.
    Generates a per‐device secret which the client must keep in secure storage.
    """
    acct = get_object_or_404(Account, user=request.user)

    # Must have already set a PIN (and done KYC)
    if not acct.pin_number or not acct.kyc_submitted:
        return Response(
            {"detail": "You must finish KYC and set a PIN before enabling fingerprint."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Generate a random 64‐char secret and enable fingerprint flag
    secret = uuid.uuid4().hex + uuid.uuid4().hex[:32]  # 96 hex chars, truncate or use only 64 if you like
    acct.fingerprint_secret  = secret
    acct.fingerprint_enabled = True
    acct.save()

    return Response(
        {"fingerprint_secret": secret},
        status=status.HTTP_200_OK
    )



# -----------------------------------------------------------------------------
# FINGERPRINTLOGIN  API Endpoint
# -----------------------------------------------------------------------------
@api_view(['POST'])
@parser_classes([JSONParser])
def fingerprint_login(request):
    """
    Step 7b: Login with fingerprint. Client presents the saved secret instead of a PIN.
    Returns JWT tokens on success.
    """
    ser = FingerprintLoginSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    secret = ser.validated_data['fingerprint_secret']

    try:
        acct = Account.objects.get(
            fingerprint_enabled=True,
            fingerprint_secret=secret,
            kyc_confirmed=True  # only allow after KYC confirmed
        )
    except Account.DoesNotExist:
        return Response({"detail": "Invalid fingerprint credential."},
                        status=status.HTTP_401_UNAUTHORIZED)

    user = acct.user
    refresh = RefreshToken.for_user(user)
    return Response({
        "access":  str(refresh.access_token),
        "refresh": str(refresh),
    }, status=status.HTTP_200_OK)




# -----------------------------------------------------------------------------
# FACIDLOGIN  API Endpoint
# -----------------------------------------------------------------------------
@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def enable_faceid(request):
    """
    Step: enable FaceID on this device.
    Generates and returns a per‐device secret.
    """
    acct = get_object_or_404(Account, user=request.user)

    if not acct.pin_number or not acct.kyc_submitted:
        return Response(
            {"detail": "Complete KYC and set a PIN before enabling Face ID."},
            status=status.HTTP_400_BAD_REQUEST
        )

    secret = uuid.uuid4().hex + uuid.uuid4().hex[:32]
    acct.faceid_secret  = secret
    acct.faceid_enabled = True
    acct.save()

    return Response({"faceid_secret": secret}, status=status.HTTP_200_OK)


@api_view(['POST'])
@parser_classes([JSONParser])
def faceid_login(request):
    """
    Login via Face ID: client supplies the stored secret.
    Returns JWT tokens if valid and KYC is confirmed.
    """
    ser = FaceIDLoginSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    token = ser.validated_data['faceid_secret']

    try:
        acct = Account.objects.get(
            faceid_enabled=True,
            faceid_secret=token,
            kyc_confirmed=True
        )
    except Account.DoesNotExist:
        return Response({"detail": "Invalid Face ID credential."},
                        status=status.HTTP_401_UNAUTHORIZED)

    refresh = RefreshToken.for_user(acct.user)
    return Response({
        "access":  str(refresh.access_token),
        "refresh": str(refresh),
    }, status=status.HTTP_200_OK)




# -----------------------------------------------------------------------------
# ACCOUNTACTIVATE API Endpoint
# -----------------------------------------------------------------------------
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def kyc_activate_view(request):
    """
    Final KYC step: activate the account so the user can start using it.
    Admin will verify the documents later.
    """
    account = get_object_or_404(Account, user=request.user)

    # must have finished all prior KYC steps
    if not account.kyc_submitted:
        return Response(
            {"detail": "Please complete and submit your KYC first."},
            status=status.HTTP_400_BAD_REQUEST
        )

    # Activate account—but do NOT set kyc_confirmed
    account.account_status = "active"
    account.save()

    # Send “your account is live” email:
    subject = "Your Blupay account is now live!"
    text_body = (
        f"Hi {request.user.get_full_name() or request.user.email},\n\n"
        f"Your account is now active and ready to use. Here are your details:\n\n"
        f"  • Account number: {account.account_number}\n"
        f"  • PIN: {account.pin_number}\n\n"
        "We’ll review your KYC documents shortly and let you know once they’re verified.\n\n"
        "— The Blupay Team"
    )
    html_body = render_to_string("emails/account_live_pending_kyc.html", {
        "user": request.user,
        "account": account,
    })

    send_mail(
        subject,
        text_body,
        settings.DEFAULT_FROM_EMAIL,
        [request.user.email],
        html_message=html_body,
    )

    serializer = AccountActivationSerializer(account)
    return Response({
        "message": "Your account is active! We’re reviewing your KYC now.",
        "account": serializer.data
    }, status=status.HTTP_200_OK)





# add NFC as a quick-action
QUICK_ACTIONS = [
    {"key": "transfer", "label": "Transfer"},
    {"key": "request",  "label": "Request"},
    {"key": "in_out",   "label": "In & Out"},
    {"key": "nfc",      "label": "NFC"},   
]

SERVICES = [
    {"key": "electricity", "label": "Electricity", "icon": "electricity"},
    {"key": "internet",    "label": "Internet",    "icon": "internet"},
    {"key": "water",       "label": "Water",       "icon": "water"},
    {"key": "ewallet",     "label": "E-Wallet",    "icon": "ewallet"},
    {"key": "assurance",   "label": "Assurance",   "icon": "assurance"},
    {"key": "shopping",    "label": "Shopping",    "icon": "shopping"},
    {"key": "deals",       "label": "Deals",       "icon": "deals"},
    {"key": "health",      "label": "Health",      "icon": "health"},
    # …etc.
]

# -----------------------------------------------------------------------------
# Dashboard API Endpoint
# -----------------------------------------------------------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard(request):
    """Enhanced dashboard with comprehensive user data"""
    user = request.user
    
    if not user.is_authenticated:
        return Response(
            {"detail": "User not authenticated. You need to log in."},
            status=status.HTTP_401_UNAUTHORIZED
        )

    # Get account
    account = get_object_or_404(Account, user=user)
    
    # Get KYC if exists
    try:
        kyc = KYC.objects.get(user=user)
        kyc_data = KYCSerializer(kyc, context={'request': request}).data
    except KYC.DoesNotExist:
        kyc_data = None

    # Get recent transactions
    recent_transactions = Transaction.objects.filter(
        reciver_account=account
    ).order_by('-date')[:5]

    # Get recent payments
    recent_payments = Payment.objects.filter(
        account=account
    ).order_by('-created_at')[:5]

    # Calculate daily usage
    today = timezone.now().date()
    daily_usage = Transaction.objects.filter(
        reciver_account=account,
        status='completed',
        date__date=today
    ).aggregate(
        total=models.Sum('amount')
    )['total'] or Decimal('0')

    # Calculate monthly usage
    current_month = timezone.now().replace(day=1).date()
    monthly_usage = Transaction.objects.filter(
        reciver_account=account,
        status='completed',
        date__date__gte=current_month
    ).aggregate(
        total=models.Sum('amount')
    )['total'] or Decimal('0')

    data = {
        "user": {
            "id": user.id,
            "email": user.email,
            "full_name": user.get_full_name() or user.email,
            "date_joined": user.date_joined,
        },
        "account": AccountSerializer(account, context={'request': request}).data,
        "kyc": kyc_data,
        "has_kyc": kyc_data is not None,
        "kyc_completion_percentage": account.kyc_completion_percentage,
        "transaction_limits": {
            "daily_limit": account.daily_limit,
            "monthly_limit": account.monthly_limit,
            "single_transaction_limit": account.single_transaction_limit,
            "daily_used": daily_usage,
            "monthly_used": monthly_usage,
            "daily_remaining": max(Decimal('0'), account.daily_limit - daily_usage),
            "monthly_remaining": max(Decimal('0'), account.monthly_limit - monthly_usage),
        },
        "quick_actions": QUICK_ACTIONS,
        "services": SERVICES,
        "recent_transactions": TransactionSerializer(recent_transactions, many=True).data,
        "recent_payments": PaymentSerializer(recent_payments, many=True, context={'request': request}).data,
        "statistics": {
            "total_transactions": Transaction.objects.filter(reciver_account=account).count(),
            "successful_transactions": Transaction.objects.filter(reciver_account=account, status='completed').count(),
            "total_payments": Payment.objects.filter(account=account).count(),
            "successful_payments": Payment.objects.filter(account=account, status__in=['SUCCESS', 'SETTLED']).count(),
        }
    }
    
    # Mask sensitive data in logs
    masked_data = mask_sensitive_data(data)
    logger.info(f"Dashboard accessed by user {user.email}")
    
    return Response(data, status=status.HTTP_200_OK)






# -----------------------------------------------------------------------------
# Additional Utility Endpoints
# -----------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def account_summary(request):
    """Get account summary with transaction statistics"""
    account = get_object_or_404(Account, user=request.user)
    
    # Get transaction statistics
    total_transactions = Transaction.objects.filter(reciver_account=account).count()
    successful_transactions = Transaction.objects.filter(
        reciver_account=account, 
        status='completed'
    ).count()
    
    # Get payment statistics
    total_payments = Payment.objects.filter(account=account).count()
    successful_payments = Payment.objects.filter(
        account=account, 
        status__in=['SUCCESS', 'SETTLED']
    ).count()
    
    # Calculate success rates
    transaction_success_rate = (
        (successful_transactions / total_transactions * 100) 
        if total_transactions > 0 else 0
    )
    payment_success_rate = (
        (successful_payments / total_payments * 100) 
        if total_payments > 0 else 0
    )
    
    return Response({
        "account_number": account.account_number,
        "account_balance": account.account_balance,
        "account_status": account.account_status,
        "kyc_status": {
            "submitted": account.kyc_submitted,
            "confirmed": account.kyc_confirmed,
            "completion_percentage": account.kyc_completion_percentage
        },
        "transaction_statistics": {
            "total": total_transactions,
            "successful": successful_transactions,
            "success_rate": round(transaction_success_rate, 2)
        },
        "payment_statistics": {
            "total": total_payments,
            "successful": successful_payments,
            "success_rate": round(payment_success_rate, 2)
        },
        "limits": {
            "daily_limit": account.daily_limit,
            "monthly_limit": account.monthly_limit,
            "single_transaction_limit": account.single_transaction_limit
        }
    }, status=status.HTTP_200_OK)




api_view(['POST'])
@permission_classes([IsAuthenticated])
def update_account_limits(request):
    """Update account transaction limits (admin only)"""
    if not request.user.is_staff:
        return Response(
            {"detail": "Permission denied. Admin access required."},
            status=status.HTTP_403_FORBIDDEN
        )
    
    account_id = request.data.get('account_id')
    if not account_id:
        return Response(
            {"error": "account_id is required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    account = get_object_or_404(Account, id=account_id)
    
    # Update limits if provided
    if 'daily_limit' in request.data:
        account.daily_limit = Decimal(str(request.data['daily_limit']))
    if 'monthly_limit' in request.data:
        account.monthly_limit = Decimal(str(request.data['monthly_limit']))
    if 'single_transaction_limit' in request.data:
        account.single_transaction_limit = Decimal(str(request.data['single_transaction_limit']))
    
    account.save()
    
    logger.info(f"Account limits updated for {account.user.email} by admin {request.user.email}")
    
    return Response({
        "message": "Account limits updated successfully",
        "limits": {
            "daily_limit": account.daily_limit,
            "monthly_limit": account.monthly_limit,
            "single_transaction_limit": account.single_transaction_limit
        }
    }, status=status.HTTP_200_OK)
