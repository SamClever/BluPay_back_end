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
    ConfirmTransferSerializer
)
from django.core.mail import EmailMultiAlternatives
from twilio.rest import Client



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
    serializer = TransactionSerializer(qs, many=True)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transaction_detail(request, pk):
    """
    GET /api/transactions/{pk}/
    """
    try:
        tx = Transaction.objects.get(
            Q(sender=request.user) | Q(reciver=request.user),
            pk=pk
        )
    except Transaction.DoesNotExist:
        return Response(
            {'error': 'Transaction not found'},
            status=status.HTTP_404_NOT_FOUND
        )

    serializer = TransactionSerializer(tx)
    return Response(serializer.data, status=status.HTTP_200_OK)




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
    return Response(
        TransactionSerializer(tx).data,
        status=status.HTTP_201_CREATED
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transaction_detail(request, tx_id):
    """
    GET /api/transactions/{tx_id}/
    """
    try:
        tx = Transaction.objects.get(transaction_id=tx_id, user=request.user)
    except Transaction.DoesNotExist:
        return Response({"detail":"Not found."}, status=status.HTTP_404_NOT_FOUND)
    return Response(TransactionSerializer(tx).data)



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
    return Response(TransactionSerializer(tx).data)