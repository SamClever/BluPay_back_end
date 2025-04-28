from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.db.models import Q
from decimal import Decimal
from django.utils import timezone
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
    AccountSearchSerializer,
    InitiateTransferSerializer,
    TransactionSerializer,
    ConfirmTransferSerializer,
    InitiateRequestSerializer
)
from django.core.mail import EmailMultiAlternatives
from twilio.rest import Client
from django.utils.translation import get_language
from weasyprint import HTML
from django.http import HttpResponse
from io import BytesIO
import babel.numbers
from xhtml2pdf import pisa


def index(request):
    return render(request, 'index.html')




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
def notification_list(request):
    notifications = Notification.objects.all()
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
    tw = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    sms_from = settings.TWILIO_PHONE_NUMBER

    # to receiver
    body = f"{sender.kyc.First_name} requests {ctx['formatted_amount']} from you. TX ID: {tx.transaction_id}"
    tw.messages.create(body=body, from_=sms_from, to=receiver.kyc.mobile)

    # to sender
    body = f"Your request for {ctx['formatted_amount']} to {ctx['receiver_name']} has been sent. TX ID: {tx.transaction_id}"
    tw.messages.create(body=body, from_=sms_from, to=sender.kyc.mobile)




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
