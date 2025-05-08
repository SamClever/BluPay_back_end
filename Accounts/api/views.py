from django.shortcuts import get_object_or_404
from userAccount.models import User
from userAccount.api.serializer import UserSerializer
from Accounts.api.serializer import *
from Accounts.models import Account, KYC
from rest_framework.decorators import api_view, permission_classes, parser_classes
from rest_framework.parsers import JSONParser, FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from rest_framework.views import APIView
from django_countries import countries
from Accounts.models import IDENTITY_TYPE
from rest_framework_simplejwt.tokens import RefreshToken
from .utils import compare_faces_aws
import uuid
from .mdes_client import provision_virtual_card
import stripe
from twilio.rest import Client
from weasyprint import HTML
from xhtml2pdf import pisa
import babel.numbers
import pyotp
from bluepay.models import VirtualCard
from datetime import datetime

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
    user = request.user
    account = get_object_or_404(Account, user=user)
    
    # fetch or init kyc
    try:
        kyc_record = user.kyc
    except KYC.DoesNotExist:
        kyc_record = None

    # GET current KYC
    if request.method == 'GET':
        if not kyc_record:
            return Response({"error": "KYC record not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = KYCSerializer(kyc_record, context={'request': request})
        return Response(serializer.data)

    # POST: Create KYC and provision MDES card
    if request.method == 'POST':
        if kyc_record is not None:
            return Response({"error": "KYC record already exists."}, status=status.HTTP_400_BAD_REQUEST)
        serializer = KYCSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        # save KYC
        kyc_record = serializer.save(user=user, account=account)
        account.kyc_submitted = True
        account.save()

        # Provision MDES virtual card
        mdes = MDESClient()
        resp = mdes.provision_card(customer_reference=str(account.id))
        token_ref  = resp.get('tokenReference')
        masked_pan = resp.get('maskedPAN')
        exp_month  = resp.get('expiryMonth')
        exp_year   = resp.get('expiryYear')
        exp_day    = calendar.monthrange(exp_year, exp_month)[1]
        expiration_date = date(exp_year, exp_month, exp_day)

        card = VirtualCard.objects.create(
            account=account,
            card_token=token_ref,
            masked_number=masked_pan,
            expiration_date=expiration_date,
            default_card=True
        )

        # Email user full details
        subject = 'Your Account & Virtual Wallet Card'
        html_message = render_to_string('emails/account_details.html', {
            'user': user,
            'wallet_number': card.masked_number,
            'pin_number': account.pin_number,
            'expiry_month': exp_month,
            'expiry_year': exp_year
        })
        send_mail(subject, '', settings.DEFAULT_FROM_EMAIL, [user.email], html_message=html_message)

        # SMS via Twilio
        sms_body = f"Your wallet card {card.masked_number} expires {exp_month:02d}/{exp_year}."
        twilio = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        twilio.messages.create(body=sms_body, from_=settings.TWILIO_PHONE_NUMBER, to=user.kyc.mobile)

        return Response({
            "message": "KYC submitted and virtual card created.",
            "kyc": serializer.data,
            "wallet_card": {
                "masked_number": card.masked_number,
                "expiry_month": exp_month,
                "expiry_year": exp_year
            }
        }, status=status.HTTP_201_CREATED)

    # PATCH: update existing KYC
    if request.method == 'PATCH':
        if not kyc_record:
            return Response({"error": "KYC record not found."}, status=status.HTTP_404_NOT_FOUND)
        serializer = KYCSerializer(kyc_record, data=request.data, partial=True, context={'request': request})
        serializer.is_valid(raise_exception=True)
        serializer.save()
        account.kyc_submitted = True
        account.save()
        return Response({"message": "KYC updated successfully.", "data": serializer.data}, status=status.HTTP_200_OK)


# -----------------------------------------------------------------------------
# KYC Step Views (1-5)
# -----------------------------------------------------------------------------

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def kyc_step1(request):
    if request.method == 'GET':
        identity_choices = [{'key': k, 'label': l} for k, l in IDENTITY_TYPE]
        countries_list = [{'code': c.alpha_2, 'name': c.name} for c in countries]
        return Response({'identity_types': identity_choices, 'countries': countries_list})

    serializer = KYCStep1Serializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    kyc = serializer.save()
    return Response({'message': 'Thank you', 'kyc': {'identity_type': kyc.identity_type, 'country': kyc.country}}, status=status.HTTP_200_OK)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
@parser_classes([MultiPartParser, FormParser])
def kyc_step2_view(request):
    kyc = get_object_or_404(KYC, user=request.user)
    if request.method == 'GET':
        return Response({'identity_image_url': request.build_absolute_uri(kyc.identity_image.url) if kyc.identity_image else None})
    if 'identity_image' not in request.FILES:
        return Response({'error': 'No file provided under "identity_image".'}, status=status.HTTP_400_BAD_REQUEST)
    serializer = KYCStep2Serializer(kyc, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    url = request.build_absolute_uri(serializer.instance.identity_image.url)
    return Response({'message': 'ID-card image uploaded.', 'identity_image_url': url}, status=status.HTTP_200_OK)


@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def kyc_step3_view(request):
    kyc = get_object_or_404(KYC, user=request.user)
    if request.method == 'GET':
        return Response({'selfie_image_url': request.build_absolute_uri(kyc.selfie_image.url) if kyc.selfie_image else None,
                         'face_verified': kyc.face_verified,'face_match_score': kyc.face_match_score})
    if 'selfie_image' not in request.FILES:
        return Response({'error': 'Please attach "selfie_image".'}, status=status.HTTP_400_BAD_REQUEST)
    serializer = KYCStep3Serializer(kyc, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    if not kyc.identity_image:
        return Response({'error': 'No ID image on file.'}, status=status.HTTP_400_BAD_REQUEST)
    match, score = compare_faces_aws(kyc.identity_image.path, kyc.selfie_image.path)
    kyc.face_verified = match
    kyc.face_match_score = score
    kyc.save()
    return Response({'message': 'Face verification complete.', 'face_verified': match, 'face_match_score': score}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def kyc_step4_view(request):
    kyc = get_object_or_404(KYC, user=request.user)
    serializer = KYCStep4Serializer(kyc, data=request.data, partial=True)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response({'message': 'Personal info submitted.', 'data': serializer.data}, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def kyc_step5_view(request):
    acct = get_object_or_404(Account, user=request.user)
    kyc = get_object_or_404(KYC, user=request.user, account=acct)
    if not acct.kyc_submitted:
        acct.kyc_submitted = True
        acct.account_status = 'pending'
        acct.save()

        
    data = KYCStep5Serializer(kyc, context={'request': request}).data
    data.update({
        'wallet_number': acct.wallet_number,
        'kyc_submitted': acct.kyc_submitted,
        'kyc_confirmed': acct.kyc_confirmed,
        'account_status': acct.account_status,
    })
    return Response(data, status=status.HTTP_200_OK)


# -----------------------------------------------------------------------------
# PIN & Security Endpoints
# -----------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def set_pin(request):
    ser = SetPinSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    acct = get_object_or_404(Account, user=request.user)
    if not acct.kyc_submitted:
        return Response({"detail": "You must finish KYC before setting PIN."}, status=status.HTTP_400_BAD_REQUEST)
    if acct.kyc_confirmed:
        return Response({"detail": "Account already verified — PIN cannot be changed."}, status=status.HTTP_400_BAD_REQUEST)
    acct.pin_number = ser.validated_data['pin']
    acct.account_status = 'pending'
    acct.save()
    subject = "Your Blupay account Wallet PIN"
    body = render_to_string("emails/account_details.html", {
        "user": request.user,
        "wallet_number": acct.wallet_number,
        "pin": acct.pin_number
    })
    send_mail(subject, body, settings.DEFAULT_FROM_EMAIL, [request.user.email], html_message=body)
    return Response({
        "message": "PIN created successfully.",
        "wallet_number": acct.wallet_number,
        "kyc_submitted": acct.kyc_submitted,
        "kyc_confirmed": acct.kyc_confirmed,
        "account_status": acct.account_status,
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
@parser_classes([JSONParser])
def enable_fingerprint(request):
    acct = get_object_or_404(Account, user=request.user)
    if not acct.pin_number or not acct.kyc_submitted:
        return Response({"detail": "You must finish KYC and set a PIN before enabling fingerprint."}, status=status.HTTP_400_BAD_REQUEST)
    secret = uuid.uuid4().hex + uuid.uuid4().hex[:32]
    acct.fingerprint_secret = secret
    acct.fingerprint_enabled = True
    acct.save()
    return Response({"fingerprint_secret": secret}, status=status.HTTP_200_OK)


@api_view(['POST'])
@parser_classes([JSONParser])
def fingerprint_login(request):
    ser = FingerprintLoginSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    secret = ser.validated_data['fingerprint_secret']
    try:
        acct = Account.objects.get(fingerprint_enabled=True, fingerprint_secret=secret, kyc_confirmed=True)
    except Account.DoesNotExist:
        return Response({"detail": "Invalid fingerprint credential."}, status=status.HTTP_401_UNAUTHORIZED)
    user = acct.user
    refresh = RefreshToken.for_user(user)
    return Response({"access": str(refresh.access_token), "refresh": str(refresh)}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def enable_faceid(request):
    acct = get_object_or_404(Account, user=request.user)
    if not acct.pin_number or not acct.kyc_submitted:
        return Response({"detail": "Complete KYC and set a PIN before enabling Face ID."}, status=status.HTTP_400_BAD_REQUEST)
    secret = uuid.uuid4().hex + uuid.uuid4().hex[:32]
    acct.faceid_secret = secret
    acct.faceid_enabled = True
    acct.save()
    return Response({"faceid_secret": secret}, status=status.HTTP_200_OK)


@api_view(['POST'])
@parser_classes([JSONParser])
def faceid_login(request):
    ser = FaceIDLoginSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    token = ser.validated_data['faceid_secret']
    try:
        acct = Account.objects.get(faceid_enabled=True, faceid_secret=token, kyc_confirmed=True)
    except Account.DoesNotExist:
        return Response({"detail": "Invalid Face ID credential."}, status=status.HTTP_401_UNAUTHORIZED)
    refresh = RefreshToken.for_user(acct.user)
    return Response({"access": str(refresh.access_token), "refresh": str(refresh)}, status=status.HTTP_200_OK)


# -----------------------------------------------------------------------------
# Account Activation Endpoint
# -----------------------------------------------------------------------------
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def kyc_activate_view(request):
    account = get_object_or_404(Account, user=request.user)
    if not account.kyc_submitted:
        return Response({"detail": "Please complete and submit your KYC first."},
                        status=status.HTTP_400_BAD_REQUEST)

    # 1. Provision through MDES
    try:
        card_data = (account.wallet_number, request.user.id)
    except Exception as e:
        return Response({"detail": f"Card provisioning failed: {str(e)}"},
                        status=status.HTTP_502_BAD_GATEWAY)

    # 2. Save to VirtualCard model
    
    exp_date = datetime.strptime(card_data["exp"], "%m%y").date()
    card = VirtualCard.objects.create(
        account=account,
        pan=card_data["pan"],
        masked_number=f"**** **** **** {card_data['pan'][-4:]}",
        expiration_date=exp_date,
        cvc=card_data["cvc"],
        token=card_data.get("token"),
        default_card=True
    )

    # 3. Update account status
    account.account_status = "active"
    account.save()

    # 4. Send email
    expiry = card.expiration_date.strftime("%m/%y")
    subject = "Your Blupay Virtual Card is Ready!"
    html_body = render_to_string("emails/account_live_pending_kyc.html", {
        "user": request.user,
        "masked_number": card.masked_number,
        "expiry": expiry,
        "cvc": card.cvc,
    })
    send_mail(subject, html_body, settings.DEFAULT_FROM_EMAIL,
              [request.user.email], html_message=html_body)

    # 5. Send SMS
    sms_body = f"Blupay: Your virtual card {card.masked_number} (exp {expiry}, CVC {card.cvc}) is now active."
    twilio = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    twilio.messages.create(
        body=sms_body,
        from_=settings.TWILIO_PHONE_NUMBER,
        to=request.user.kyc.mobile
    )

    # 6. Return response
    serializer = AccountActivationSerializer(account)
    return Response({
        "message": "Your account is active, and your virtual card has been provisioned!",
        "account": serializer.data,
        "wallet_card": {
            "masked_number": card.masked_number,
            "expiry": expiry,
            "cvc": card.cvc
        }
    }, status=status.HTTP_200_OK)


# -----------------------------------------------------------------------------
# Dashboard API Endpoint
# -----------------------------------------------------------------------------

QUICK_ACTIONS = [
    {"key": "transfer", "label": "Transfer"},
    {"key": "request", "label": "Request"},
    {"key": "in_out", "label": "In & Out"},
    {"key": "nfc", "label": "NFC"},
]

SERVICES = [
    {"key": "electricity", "label": "Electricity", "icon": "electricity"},
    {"key": "internet", "label": "Internet", "icon": "internet"},
    {"key": "water", "label": "Water", "icon": "water"},
    {"key": "ewallet", "label": "E-Wallet", "icon": "ewallet"},
    {"key": "assurance", "label": "Assurance", "icon": "assurance"},
    {"key": "shopping", "label": "Shopping", "icon": "shopping"},
    {"key": "deals", "label": "Deals", "icon": "deals"},
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

