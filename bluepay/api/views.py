from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status, throttling, permissions
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from rest_framework import permissions, generics
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.db.models import Q
from decimal import Decimal, InvalidOperation
from rest_framework.decorators import action
from django.contrib.auth import authenticate
import decimal
from django.utils import timezone
from datetime import timedelta
from Accounts.models import *
from bluepay.models import *
from bluepay.models import (
    Transaction, 
    Notification,
    VirtualCard,
    PaymentTransaction,
    NFCDevice,
    PaymentToken,
    )
from .serializers import (
    VirtualCardSerializer,
    PaymentTransactionSerializer,
    NFCDeviceSerializer,
    PaymentTokenSerializer,            
    NotificationSerializer,
    NotificationSettingSerializer,
    AccountSearchSerializer,
    InitiateTransferSerializer,
    TransactionSerializer,
    ConfirmTransferSerializer,
    InitiateRequestSerializer,
    VirtualCardCreateSerializer,
    TopUpSerializer,
    WithdrawSerializer,
    SecuritySettingSerializer,
    ChangePasswordSerializer,
    ChangePinSerializer,

)
from django.core.mail import EmailMultiAlternatives
from twilio.rest import Client
from django.utils.translation import get_language
from weasyprint import HTML
from django.http import HttpResponse
from io import BytesIO
import babel.numbers
from xhtml2pdf import pisa
import requests
from .helpers import send_notification
import pyotp



def index(request):
    return render(request, 'index.html')


import stripe, tap_sdk   # assuming python SDKs

stripe.api_key    = settings.STRIPE_SECRET_KEY
# clickpesa.api_key = settings.CLICKPESA_SECRET_KEY
# tap = tap_sdk.Client(api_key=settings.TAP_SECRET_KEY)


# ---------------------------------------------------------------------
# Transaction API Endpoints
# ---------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transaction_list(request):
    """
    GET /api/transactions/?type=transfer|request
    """
    tx_type = request.query_params.get('type')
    qs = Transaction.objects.filter(
        Q(sender=request.user) | Q(reciver=request.user)
    )
    if tx_type in ('transfer', 'request'):
        qs = qs.filter(transaction_type=tx_type)
    qs = qs.order_by('-date')
    serializer = TransactionSerializer(qs, many=True,
        context={'request': request, 'locale': request.LANGUAGE_CODE})
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transaction_detail(request, tx_id):
    """
    GET /transactions/{transaction_id}/
    """
    try:
        tx = Transaction.objects.get(
            Q(transaction_id=tx_id),
            Q(sender=request.user) | Q(reciver=request.user)
        )
    except Transaction.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

    serializer = TransactionSerializer(tx, context={'request': request, 'locale': request.LANGUAGE_CODE})
    return Response(serializer.data)




# ---------------------------------------------------------------------
# Virtual Card API Endpoints
# ---------------------------------------------------------------------

@api_view(['GET', 'POST'])
@permission_classes([IsAuthenticated])
def virtualcard(request):
    """
    List all virtual cards for the authenticated user or create a new one.
    """
    user = request.user
    account = get_object_or_404(Account, user=user)
    
    if request.method == 'GET':
        cards = VirtualCard.objects.filter(account=account)
        serializer = VirtualCardSerializer(cards, many=True, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method == 'POST':
        serializer = VirtualCardSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():

            card = serializer.save()
            # Create notification for adding a card.
            Notification.objects.create(
                user=user,
                notification_type="Added Credit Card",
                amount=0  # Amount is optional.
            )

            # Send email notification.
            subject = "Virtual Card Added"
            # Optionally, render an HTML template for a better email message.
            message = f"Dear {user.first_name or user.email},\n\nYour new virtual card ending with {card.masked_number[-4:]} has been added successfully."
            html_message = render_to_string('emails/virtual_card_added.html', {
                'user': user,
                'card': card,
            })
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email], html_message=html_message)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



@api_view(['GET', 'PUT', 'PATCH', 'DELETE'])
@permission_classes([IsAuthenticated])
def virtualcard_detail(request, pk):
    """
    Retrieve, update, or delete a virtual card.
    """
    # Fetch the card; return 404 if not found.
    card = get_object_or_404(VirtualCard, pk=pk)
    
    # Ensure the card belongs to the authenticated user.
    if card.account.user != request.user:
        return Response({'error': 'Permission denied.'}, status=status.HTTP_403_FORBIDDEN)
    
    if request.method == 'GET':
        serializer = VirtualCardSerializer(card, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    elif request.method in ['PUT', 'PATCH']:
        partial = (request.method == 'PATCH')
        serializer = VirtualCardSerializer(card, data=request.data, partial=partial, context={'request': request})
        if serializer.is_valid():
            serializer.save()

            # Create notification for updating a card.
            Notification.objects.create(
                user=request.user,
                notification_type="Updated Credit Card",  # Choose a suitable type for an update.
                amount=0
            )


            # Send email notification.
            subject = "Virtual Card Updated"
            message = f"Dear {request.user.first_name or request.user.email},\n\nYour virtual card ending with {card.masked_number[-4:]} has been updated successfully."
            html_message = render_to_string('emails/virtual_card_updated.html', {
                'user': request.user,
                'card': card,
            })
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [request.user.email], html_message=html_message)
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    elif request.method == 'DELETE':
        masked_last4 = card.masked_number[-4:]
        card.delete()
        
        Notification.objects.create(
            user=request.user,
            notification_type="Deleted Credit Card",
            amount=0
        )

        # send_notification(
        #     user=request.user,
        #     notification_type="payment_success",
        #     title="Payment Successful",
        #     message="Your payment of $20 was successful.",
        #     amount=20
        # )

        # Send email notification.
        subject = "Virtual Card Deleted"
        message = f"Dear {request.user.first_name or request.user.email},\n\nYour virtual card ending with {masked_last4} has been deleted."
        html_message = render_to_string('emails/virtual_card_deleted.html', {
            'user': request.user,
            'masked_last4': masked_last4,
        })
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [request.user.email], html_message=html_message)
        return Response(status=status.HTTP_204_NO_CONTENT)



# ---------------------------------------------------------------------
# Payment Transaction API Endpoints
# ---------------------------------------------------------------------

@api_view(['GET'])
def payment_transaction_list(request):
    transactions = PaymentTransaction.objects.all()
    serializer = PaymentTransactionSerializer(transactions, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def payment_transaction_detail(request, pk):
    try:
        transaction = PaymentTransaction.objects.get(pk=pk)
    except PaymentTransaction.DoesNotExist:
        return Response({'error': 'Transaction not found'}, status=status.HTTP_404_NOT_FOUND)
    serializer = PaymentTransactionSerializer(transaction)
    return Response(serializer.data)





# ---------------------------------------------------------------------
# NFC Device API Endpoints
# ---------------------------------------------------------------------

@api_view(['GET'])
def nfcdevice_list(request):
    devices = NFCDevice.objects.all()
    serializer = NFCDeviceSerializer(devices, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def nfcdevice_detail(request, pk):
    try:
        device = NFCDevice.objects.get(pk=pk)
    except NFCDevice.DoesNotExist:
        return Response({'error': 'NFC Device not found'}, status=status.HTTP_404_NOT_FOUND)
    serializer = NFCDeviceSerializer(device)
    return Response(serializer.data)



# ---------------------------------------------------------------------
# Payment Token API Endpoints
# ---------------------------------------------------------------------
@api_view(['GET'])
def paymenttoken_list(request):
    tokens = PaymentToken.objects.all()
    serializer = PaymentTokenSerializer(tokens, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def paymenttoken_detail(request, pk):
    try:
        token = PaymentToken.objects.get(pk=pk)
    except PaymentToken.DoesNotExist:
        return Response({'error': 'Payment Token not found'}, status=status.HTTP_404_NOT_FOUND)
    serializer = PaymentTokenSerializer(token)
    return Response(serializer.data)




# ---------------------------------------------------------------------
# Notification API Endpoint
# ---------------------------------------------------------------------
@api_view(['GET'])
@permission_classes([IsAuthenticated])
def notification_list(request):
    notifications = Notification.objects.filter(user=request.user)
    serializer = NotificationSerializer(notifications, many=True)
    return Response(serializer.data)



@api_view(['GET'])
def notification_detail(request, pk):
    try:
        notification = Notification.objects.get(pk=pk)
    except Notification.DoesNotExist:
        return Response({'error': 'Notification not found'}, status=status.HTTP_404_NOT_FOUND)
    serializer = NotificationSerializer(notification)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_notification_read(request, nid):
    try:
        notification = Notification.objects.get(nid=nid, user=request.user)
        notification.is_read = True
        notification.save()
        return Response({"status": "marked as read"})
    except Notification.DoesNotExist:
        return Response({"error": "Notification not found"}, status=status.HTTP_404_NOT_FOUND)
    





class NotificationSettingDetail(generics.RetrieveUpdateAPIView):
    """
    GET  /api/notification-settings/    → read all toggles
    PATCH/PUT /api/notification-settings/ → update any subset
    """
    serializer_class = NotificationSettingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # ensure one exists:
        setting, _ = NotificationSettings.objects.get_or_create(user=self.request.user)
        return setting




# ---------------------------------------------------------------------
# SEARCH API Endpoints
# ---------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def search_account(request):
    """
    POST { "query": "..." }
     → search by account_number, user.email, kyc.First_name,
       and only include accounts with kyc_confirmed=True.
    """
    q = request.data.get('query', '').strip()
    if not q:
        return Response(
            {"detail": "Please provide a non-empty search query."},
            status=status.HTTP_400_BAD_REQUEST
        )

    qs = Account.objects.filter(
        Q(account_number__iexact=q)    |
        Q(user__email__icontains=q)    |
        Q(kyc__First_name__icontains=q),
        kyc_confirmed=True
    ).distinct()

    if not qs.exists():
        return Response(
            {"detail": "No matching accounts found."},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = AccountSearchSerializer(qs, many=True, context={'request': request})
    return Response(serializer.data, status=status.HTTP_200_OK)




# ---------------------------------------------------------------------
# TRANSFER API Endpoints
# ---------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_transfer(request):
    """
    POST { account_number, amount, description? } → creates TX with status="processing"
    """
    serializer = InitiateTransferSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    tx = serializer.save()
    out = TransactionSerializer(
        tx,
        context={'request': request, 'locale': get_language()}
    )
    return Response(out.data, status=201)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transaction_detail(request, tx_id):
    """
    GET /api/transactions/{tx_id}/
    """
    try:
        tx = Transaction.objects.get(transaction_id=tx_id, user=request.user,)
    except Transaction.DoesNotExist:
        return Response({"detail":"Not found."}, status=status.HTTP_404_NOT_FOUND)
    return Response(TransactionSerializer(tx, context={'request': request, 'locale': request.LANGUAGE_CODE}).data)



@api_view(['POST'])
@permission_classes([IsAuthenticated])
def confirm_transfer(request, tx_id):
    """
    POST /api/transactions/{tx_id}/confirm/ { pin_number }
    """
    # 1) Lookup transaction
    try:
        tx = Transaction.objects.get(transaction_id=tx_id, user=request.user)
    except Transaction.DoesNotExist:
        return Response({"detail":"Transaction not found."}, status=status.HTTP_404_NOT_FOUND)

    # 2) Validate PIN and status
    serializer = ConfirmTransferSerializer(
        data=request.data,
        context={'request': request, 'transaction': tx}
    )
    serializer.is_valid(raise_exception=True)

    # 3) Finalize transaction
    tx = serializer.save()

    out = TransactionSerializer(
        tx,
        context={'request': request, 'locale': request.LANGUAGE_CODE}
    )

    # 4) Prepare context for templates
    sender    = tx.sender
    recipient = tx.reciver
    ctx = {
        'sender_name'     : f"{sender.get_full_name() or sender.email}",
        'recipient_name'  : f"{recipient.get_full_name() or recipient.email}",
        'amount'          : tx.amount,
        'transaction_id'  : tx.transaction_id,
        'date'            : tx.date.strftime("%Y-%m-%d %H:%M:%S"),
    }

    # ────────────────────────────────────────────────────────────
    # 5A) Send e-mail to SENDER
    subject = f"You sent {tx.amount} to {ctx['recipient_name']}"
    text    = render_to_string('emails/transfer_sent.txt', ctx)
    html    = render_to_string('emails/transfer_sent.html', ctx)
    mail    = EmailMultiAlternatives(
                  subject,
                  text,
                  settings.DEFAULT_FROM_EMAIL,
                  [sender.email],
              )
    mail.attach_alternative(html, "text/html")
    mail.send()

    # 5B) Send e-mail to RECEIVER
    subject = f"You received {tx.amount} from {ctx['sender_name']}"
    text    = render_to_string('emails/transfer_received.txt', ctx)
    html    = render_to_string('emails/transfer_received.html', ctx)
    mail    = EmailMultiAlternatives(
                  subject,
                  text,
                  settings.DEFAULT_FROM_EMAIL,
                  [recipient.email],
              )
    mail.attach_alternative(html, "text/html")
    mail.send()

    # # ────────────────────────────────────────────────────────────
    # # 6) Send SMS via Twilio
    twilio = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)

    sms_from = settings.TWILIO_PHONE_NUMBER
    # a) SMS to sender
    sms_body = (
        f"You sent {tx.amount} to {ctx['recipient_name']}. "
        f"TX ID: {tx.transaction_id}"
    )
    twilio.messages.create(
        body=sms_body,
        from_=sms_from,
        to=sender.kyc.mobile   # assuming you store E.164 in .mobile
    )

    # b) SMS to receiver
    sms_body = (
        f"You received {tx.amount} from {ctx['sender_name']}. "
        f"TX ID: {tx.transaction_id}"
    )
    twilio.messages.create(
        body=sms_body,
        from_=sms_from,
        to=recipient.kyc.mobile
    )

    # ────────────────────────────────────────────────────────────
    # 7) Return the updated transaction back to the client
    return Response(out.data)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_receipt(request, tx_id):
    # 1) Fetch & authorize
    try:
        tx = Transaction.objects.get(
            Q(transaction_id=tx_id),
            Q(sender=request.user) | Q(reciver=request.user)
        )
    except Transaction.DoesNotExist:
        return Response({"detail": "Not found."}, status=404)

    # 2) Serialize for template context
    serializer = TransactionSerializer(
        tx,
        context={'request': request, 'locale': request.LANGUAGE_CODE}
    )
    data = serializer.data

    # 3) Render HTML
    html_string = render_to_string('receipt.html', {'transaction': data})

    # 4) Convert to PDF
    pdf_file = HTML(string=html_string).write_pdf()

    # 5) Return as attachment
    resp = HttpResponse(pdf_file, content_type='application/pdf')
    resp['Content-Disposition'] = (
        f'attachment; filename="receipt_{tx.transaction_id}.pdf"'
    )
    return resp



# ---------------------------------------------------------------------
# PAYMENT REQUEST API Endpoints
# ---------------------------------------------------------------------
def _send_request_notifications(tx):
    sender    = tx.sender
    receiver  = tx.reciver
    ctx = {
        "tx": tx,
        "formatted_amount": babel.numbers.format_currency(
            tx.amount, tx.currency_code, sender.account.user.profile.locale.replace("-", "_")
        ) if hasattr(settings, "USE_BABEL") else f"{tx.amount} {tx.currency_code}",
        "date": tx.date.strftime("%b %d, %Y | %I:%M:%S %p"),
        "sender_name": f"{sender.kyc.First_name} {sender.kyc.Last_name or ''}",
        "receiver_name": f"{receiver.kyc.First_name} {receiver.kyc.Last_name or ''}",
    }

    # --- Email to RECEIVER ---
    subject = f"You have a new payment request of {ctx['formatted_amount']}"
    text    = render_to_string("emails/request_received.txt", ctx)
    html    = render_to_string("emails/request_received.html", ctx)
    mail    = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [receiver.email])
    mail.attach_alternative(html, "text/html")
    mail.send()

    # --- Email to SENDER ---
    subject = f"Your payment request to {ctx['receiver_name']} was sent"
    text    = render_to_string("emails/request_sent.txt", ctx)
    html    = render_to_string("emails/request_sent.html", ctx)
    mail    = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [sender.email])
    mail.attach_alternative(html, "text/html")
    mail.send()

    # --- SMS via Twilio ---
    # tw = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    # sms_from = settings.TWILIO_PHONE_NUMBER

    # # to receiver
    # body = f"{sender.kyc.First_name} requests {ctx['formatted_amount']} from you. TX ID: {tx.transaction_id}"
    # tw.messages.create(body=body, from_=sms_from, to=receiver.kyc.mobile)

    # # to sender
    # body = f"Your request for {ctx['formatted_amount']} to {ctx['receiver_name']} has been sent. TX ID: {tx.transaction_id}"
    # tw.messages.create(body=body, from_=sms_from, to=sender.kyc.mobile)




@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_request(request):
    """
    POST /api/requests/  → creates TX of type=request & status=processing
    """
    serializer = InitiateRequestSerializer(data=request.data, context={'request': request})
    serializer.is_valid(raise_exception=True)
    tx = serializer.save()
    _send_request_notifications(tx)
    out = TransactionSerializer(tx, context={'request': request})
    return Response(out.data, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def download_request_receipt(request, tx_id):
    """
    GET /api/requests/{tx_id}/receipt/  → application/pdf
    """
    tx = Transaction.objects.select_related(
        'sender__kyc','reciver__kyc','sender_account','reciver_account'
    ).filter(
        transaction_id=tx_id,
        transaction_type="request"
    ).filter(
        Q(sender=request.user) | Q(reciver=request.user)
    ).first()
    if not tx:
        return Response({"detail":"Not found."}, status=status.HTTP_404_NOT_FOUND)

    # format amount
    try:
        locale = request.LANGUAGE_CODE.replace("-", "_")
        formatted = babel.numbers.format_currency(tx.amount, tx.currency_code, locale=locale)
    except:
        formatted = f"{tx.amount} {tx.currency_code}"

    html = render_to_string("request_receipt.html", {
        "tx": tx,
        "tx_formatted_amount": formatted,
        "now": timezone.now(),
    })

    buf = BytesIO()
    if pisa.CreatePDF(html, dest=buf).err:
        return HttpResponse("PDF generation error", status=500)
    buf.seek(0)
    resp = HttpResponse(buf, content_type="application/pdf")
    resp["Content-Disposition"] = f'attachment; filename="request_{tx.transaction_id}.pdf"'
    return resp





@api_view(['PATCH'])
@permission_classes([IsAuthenticated])
def settle_request(request, account_number, transaction_id):
    """
    PATCH  /api/accounts/{account_number}/transactions/{transaction_id}/settle/
    Marks a pending transaction as completed by the receiver.
    """
    account = get_object_or_404(Account, account_number=account_number)
    # filter on the real FK field:
    tx = get_object_or_404(
        Transaction,
        transaction_id=transaction_id,
        reciver_account=account
    )

    # only the owner of that account may settle
    if request.user != account.user:
        return Response(
            {"detail": "You do not have permission to settle this request."},
            status=status.HTTP_403_FORBIDDEN
        )

    if tx.status != 'pending':
        return Response(
            {"detail": f"Cannot settle a transaction in status '{tx.status}'."},
            status=status.HTTP_400_BAD_REQUEST
        )

    tx.status = 'completed'
    tx.save()
    return Response(TransactionSerializer(tx).data, status=status.HTTP_200_OK)


@api_view(['DELETE'])
@permission_classes([IsAuthenticated])
def delete_request(request, account_number, transaction_id):
    """
    DELETE /api/accounts/{account_number}/transactions/{transaction_id}/
    Deletes a transaction (sender only).
    """
    account = get_object_or_404(Account, account_number=account_number)
    # the “sender” side of that FK
    tx = get_object_or_404(
        Transaction,
        transaction_id=transaction_id,
        sender_account=account
    )

    if request.user != account.user:
        return Response(
            {"detail": "You do not have permission to delete this request."},
            status=status.HTTP_403_FORBIDDEN
        )

    tx.delete()
    return Response(status=status.HTTP_204_NO_CONTENT)







# ---------------------------------------------------------------------
# VirtualCardCreateSerializer API Endpoints
# ---------------------------------------------------------------------
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_virtual_card(request):
    """
    POST /api/virtual-cards/  
    payload: {
      "card_number": "4242424242424242",
      "exp_month": 2,
      "exp_year": 2030,
      "cvc": "123",
      "card_name": "My Blue Visa"
    }
    """
    serializer = VirtualCardCreateSerializer(data=request.data, context={'request': request})
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    card = serializer.save()

    # 1) create a notification
    Notification.objects.create(
        user=request.user,
        notification_type="Added Virtual Card",
        amount=0,
    )

    # 2) send email (text + HTML)
    subject   = "Your Virtual Card is Ready!"
    from_email = settings.DEFAULT_FROM_EMAIL
    to = [request.user.email]

    text_body = render_to_string('emails/virtual_card_added.txt', {
        'user':    request.user,
        'card':    card,
        'request': request,
    })
    html_body = render_to_string('emails/virtual_card_added.html', {
        'user':    request.user,
        'card':    card,
        'request': request,
    })

    email = EmailMultiAlternatives(subject, text_body, from_email, to)
    email.attach_alternative(html_body, "text/html")
    email.send()

    # 3) return the fully serialized card back to client
    out = VirtualCardSerializer(card, context={'request': request})
    return Response(out.data, status=status.HTTP_201_CREATED)







@api_view(['POST'])
@permission_classes([IsAuthenticated])
def add_card(request):
    """
    POST /api/cards/add/
    Body: { "stripe_token": "tok_visa", "card_name": "My Blue Visa" }
    """
    user = request.user
    account = Account.objects.get(user=user)

    token = request.data.get('stripe_token')
    if not token:
        return Response({"error": "stripe_token is required"}, status=status.HTTP_400_BAD_REQUEST)

    # 1) Ensure a Stripe Customer exists
    if not account.stripe_customer_id:
        cust = stripe.Customer.create(email=user.email)
        account.stripe_customer_id = cust.id
        account.save()
    else:
        cust = stripe.Customer.retrieve(account.stripe_customer_id)

    # 2) Attach the card to the customer
    stripe_card = stripe.Customer.create_source(cust.id, source=token)

    # 3) Persist in our DB
    vc = VirtualCard.objects.create(
        account=account,
        card_token=stripe_card.id,
        card_name=request.data.get('card_name', ""),
        masked_number=f"•••• •••• •••• {stripe_card.last4}",
        expiration_date=f"{stripe_card.exp_year}-{stripe_card.exp_month:02d}-01",  # or parse properly
        card_type=stripe_card.brand.lower().replace(" ", "_"),
    )

    serializer = VirtualCardSerializer(vc, context={'request': request})
    return Response(serializer.data, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def top_up(request):
    """
    POST /api/accounts/top-up/
    Body: { "card_id": "<virtual-card-id>", "amount": "100.00", "currency": "USD" }
    """
    user    = request.user
    account = Account.objects.get(user=user)
    vc_id   = request.data.get('card_id')
    amt_str = request.data.get('amount')
    curr    = request.data.get('currency', account.default_currency_code)

    if not vc_id or not amt_str:
        return Response({"error": "card_id and amount are required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        vc     = VirtualCard.objects.get(pk=vc_id, account=account, active=True)
        amount = Decimal(amt_str)
    except (VirtualCard.DoesNotExist, InvalidOperation):
        return Response({"error": "Invalid card or amount"}, status=status.HTTP_400_BAD_REQUEST)

    # 1) Create a Stripe charge
    charge = stripe.Charge.create(
        amount=int(amount * 100),
        currency=curr.lower(),
        customer=account.stripe_customer_id,
        source=vc.card_token,
        description=f"Top-up Blupay account via card {vc.masked_number}"
    )

    if charge.status != 'succeeded':
        return Response({"error": "Charge failed"}, status=status.HTTP_402_PAYMENT_REQUIRED)

    # 2) Update our balance
    account.account_balance += amount
    account.save()

    # 3) Log the payment transaction
    pt = PaymentTransaction.objects.create(
        account=account,
        virtual_card=vc,
        amount=amount,
        transaction_type='purchase',
        status='completed',
        description=f"Top-up via {vc.masked_number}"
    )

    return Response({
        "new_balance": str(account.account_balance),
        "transaction_id": pt.transaction_id
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def withdraw(request):
    """
    POST /api/accounts/withdraw/
    Body: { "amount": "50.00", "currency": "USD", "destination": "<stripe-bank-account-id>" }
    NOTE: for real bank payouts you’ll need Stripe Connect.
    """
    user    = request.user
    account = Account.objects.get(user=user)
    amt_str = request.data.get('amount')
    curr    = request.data.get('currency', account.default_currency_code)
    dest    = request.data.get('destination')

    if not amt_str or not dest:
        return Response({"error": "amount and destination are required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        amount = Decimal(amt_str)
    except Decimal.InvalidOperation:
        return Response({"error": "Invalid amount"}, status=status.HTTP_400_BAD_REQUEST)

    if account.account_balance < amount:
        return Response({"error": "Insufficient funds"}, status=status.HTTP_400_BAD_REQUEST)

    # 1) Create a Payout (you must have Stripe Connect)
    try:
        payout = stripe.Payout.create(
            amount=int(amount * 100),
            currency=curr.lower(),
            destination=dest,
            method="standard"
        )
    except stripe.error.StripeError as e:
        return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    # 2) Deduct balance
    account.account_balance -= amount
    account.save()

    # 3) Log the withdrawal
    pt = PaymentTransaction.objects.create(
        account=account,
        amount=amount,
        transaction_type='refund',  # or 'transfer'
        status='completed',
        description=f"Withdraw to {dest}"
    )

    return Response({
        "new_balance": str(account.account_balance),
        "payout_id": payout.id
    }, status=status.HTTP_200_OK)






#` ---------------------------------------------------------------------
# SECURITY API Endpoints
# ---------------------------------------------------------------------
class SecuritySettingDetail(generics.RetrieveUpdateAPIView):
    """
    GET  /api/security/       → read toggles
    PATCH       /api/security/ → update remember_me / face_id / biometric_id
    """
    serializer_class = SecuritySettingSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        setting, _ = SecuritySetting.objects.get_or_create(user=self.request.user)
        return setting

    @action(detail=False, methods=["POST"], url_path="google-auth/setup")
    def setup_google_auth(self, request):
        """
        POST /api/security/google-auth/setup/
        → returns a TOTP provisioning URI (and QR-code URL) for the client
        """
        setting = self.get_object()
        # generate a new base32 secret and save
        secret = pyotp.random_base32(length=32)
        setting.ga_secret = secret
        setting.save(update_fields=["ga_secret"])

        otpauth = pyotp.totp.TOTP(secret).provisioning_uri(
            name=request.user.email, issuer_name="Bluepay"
        )
        return Response({"otpauth_url": otpauth})

    @action(detail=False, methods=["POST"], url_path="google-auth/verify")
    def verify_google_auth(self, request):
        """
        POST /api/security/google-auth/verify/
        { code: '123456' } → on success, flip ga_enabled=True
        """
        code = request.data.get("code")
        setting = self.get_object()
        totp = pyotp.TOTP(setting.ga_secret or "")
        if totp.verify(code):
            setting.ga_enabled = True
            setting.save(update_fields=["ga_enabled"])
            return Response({"detail": "Google Authenticator enabled."})
        return Response({"detail": "Invalid code."}, status=status.HTTP_400_BAD_REQUEST)
    

class ChangePasswordView(generics.GenericAPIView):
    """
    POST /api/security/change-password/
    Throttled, validated, with confirmation email.
    """
    serializer_class = ChangePasswordSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [throttling.UserRateThrottle]

    def post(self, request):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)

        user = request.user
        if not user.check_password(ser.validated_data["old_password"]):
            return Response(
                {"old_password": "Wrong password."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user.set_password(ser.validated_data["new_password"])
        user.save()

        # Send email only (no SMS for password)
        subject = "Your password has been changed"
        context = {"user": user}
        text_body = render_to_string("emails/password_changed.txt", context)
        html_body = render_to_string("emails/password_changed.html", context)
        send_mail(
            subject,
            text_body,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            html_message=html_body,
        )

        return Response({"detail": "Password have been changed successfully."})




class ChangePinView(generics.GenericAPIView):
    """
    POST /api/security/change-pin/
    Throttled, validated, with email+SMS on success.
    """
    serializer_class = ChangePinSerializer
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [throttling.UserRateThrottle]

    def post(self, request):
        ser = self.get_serializer(data=request.data)
        ser.is_valid(raise_exception=True)
        # Validate old PIN
        old = ser.validated_data["old_pin"]
        new = ser.validated_data["new_pin1"]

        account = Account.objects.get(user=request.user)
        if not account.check_pin(old):
            return Response(
                {"old_pin": "Incorrect PIN."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Hash & save new PIN
        account.set_pin(new)
        account.save(update_fields=["pin_hash", "pin_number"])

        # Send email
        subject    = "Your PIN has been changed"
        context    = {
            "user": request.user,
            "masked_pin": f"•••• {new[-2:]}"
        }
        text_body  = render_to_string("emails/pin_changed.txt", context)
        html_body  = render_to_string("emails/pin_changed.html", context)
        send_mail(
            subject,
            text_body,
            settings.DEFAULT_FROM_EMAIL,
            [request.user.email],
            html_message=html_body,
        )

        # Send SMS
        # if account.mobile:
        #     tw = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        #     tw.messages.create(
        #         to=account.mobile,
        #         from_=settings.TWILIO_FROM_NUMBER,
        #         body=f"Hi {user.first_name}, your wallet PIN was successfully changed."
        #     )

        return Response({"detail": "PIN changed successfully."})