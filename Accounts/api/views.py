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
from django.core.mail import send_mail
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
    # """
    # Screen 1 of KYC: choose identity type & country.
    # """
    
    # if request.method == 'GET':
    #     # build the identity‐type choices
    #     identity_choices = [
    #         {'key': key, 'label': label}
    #         for key, label in IDENTITY_TYPE
    #     ]
    #     # build a simple country list from pycountry
    #     countries = [
    #         {'code': c.alpha_2, 'name': c.name}
    #         for c in pycountry.countries
    #     ]
    #     return Response({
    #         'identity_types': identity_choices,
    #         'countries': countries
    #     })

    # # POST: user has chosen their type & country
    # serializer = KYCStep1Serializer(data=request.data)
    # if not serializer.is_valid():
    #     return Response(serializer.errors, status=400)

    # kyc = serializer.update_kyc(request.user)
    # return Response({
    #     'message': 'thank you for choosing your identity type & country',
    #     'kyc': {
    #         'identity_type': kyc.identity_type,
    #         'country': kyc.country,
    #     }
    # })





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

    kyc = get_object_or_404(KYC, user=request.user, account=acct)

    
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
    # Get the current user from the request.
    user = request.user
    # Although the permission ensures the user is authenticated,
    if not user.is_authenticated:
        return Response(
            {"detail": "User not authenticated. You need to log in."},
            status=status.HTTP_401_UNAUTHORIZED
        )

    
    # Ensure a KYC record exists for this user.
    try:
        kyc = KYC.objects.get(user=user)
    except KYC.DoesNotExist:
        return Response(
            {"detail": "You need to submit your KYC."},
            status=status.HTTP_404_NOT_FOUND
        )

    # Retrieve the associated account.
    account = get_object_or_404(Account, user=user)

    # Assuming Transaction and CreditCard models exist and corresponding serializers are set up.
    # recent_transfer = Transaction.objects.filter(
    #     sender=user, transaction_type="transfer", status="completed"
    # ).order_by("-id").first()
    # recent_received_transfer = Transaction.objects.filter(
    #     reciver=user, transaction_type="transfer"
    # ).order_by("-id").first()

    # sender_transactions = Transaction.objects.filter(sender=user, transaction_type="transfer").order_by("-id")
    # receiver_transactions = Transaction.objects.filter(reciver=user, transaction_type="transfer").order_by("-id")
    # request_sender_transactions = Transaction.objects.filter(sender=user, transaction_type="request")
    # request_receiver_transactions = Transaction.objects.filter(reciver=user, transaction_type="request")
    # credit_cards = CreditCard.objects.filter(user=user).order_by("-id")
        
    data = {
        "account": AccountSerializer(account).data,
        "kyc": KYCSerializer(kyc, context={'request': request}).data,
        "quick_actions": QUICK_ACTIONS,
        "services":      SERVICES,
        # "recent_transfer": TransactionSerializer(recent_transfer).data if recent_transfer else None,
        # "recent_received_transfer": TransactionSerializer(recent_received_transfer).data if recent_received_transfer else None,
        # "sender_transactions": TransactionSerializer(sender_transactions, many=True).data,
        # "receiver_transactions": TransactionSerializer(receiver_transactions, many=True).data,
        # "request_sender_transactions": TransactionSerializer(request_sender_transactions, many=True).data,
        # "request_receiver_transactions": TransactionSerializer(request_receiver_transactions, many=True).data,
        # "credit_cards": CreditCardSerializer(credit_cards, many=True).data,
    }
    return Response(data, status=status.HTTP_200_OK)

