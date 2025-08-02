from django.shortcuts import render
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from django.shortcuts import get_object_or_404
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.timezone import now
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.conf import settings
from django.db.models import Q
import hashlib
import hmac
import json
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
    ConfirmTransferSerializer,
)
from django.utils.crypto import get_random_string
import requests

def index(request):
    return render(request, "index.html")


# ---------------------------------------------------------------------
# Transaction API Endpoints
# ---------------------------------------------------------------------


@api_view(["GET"])
def transaction_list(request):
    transactions = Transaction.objects.all()
    serializer = TransactionSerializer(transactions, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def transaction_detail(request, pk):
    try:
        transaction = Transaction.objects.get(pk=pk)
    except Transaction.DoesNotExist:
        return Response(
            {"error": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND
        )
    serializer = TransactionSerializer(transaction)
    return Response(serializer.data)


# ---------------------------------------------------------------------
# Virtual Card API Endpoints
# ---------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def virtualcard(request):
    """
    List all virtual cards for the authenticated user or create a new one.
    """
    user = request.user
    account = get_object_or_404(Account, user=user)

    if request.method == "GET":
        cards = VirtualCard.objects.filter(account=account)
        serializer = VirtualCardSerializer(
            cards, many=True, context={"request": request}
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method == "POST":
        serializer = VirtualCardSerializer(
            data=request.data, context={"request": request}
        )
        if serializer.is_valid():

            card = serializer.save()
            # Create notification for adding a card.
            Notification.objects.create(
                user=user,
                notification_type="Added Credit Card",
                amount=0,  # Amount is optional.
            )

            # Send email notification.
            subject = "Virtual Card Added"
            # Optionally, render an HTML template for a better email message.
            message = f"Dear {user.first_name or user.email},\n\nYour new virtual card ending with {card.masked_number[-4:]} has been added successfully."
            html_message = render_to_string(
                "emails/virtual_card_added.html",
                {
                    "user": user,
                    "card": card,
                },
            )
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [user.email],
                html_message=html_message,
            )
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(["GET", "PUT", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated])
def virtualcard_detail(request, pk):
    """
    Retrieve, update, or delete a virtual card.
    """
    # Fetch the card; return 404 if not found.
    card = get_object_or_404(VirtualCard, pk=pk)

    # Ensure the card belongs to the authenticated user.
    if card.account.user != request.user:
        return Response(
            {"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN
        )

    if request.method == "GET":
        serializer = VirtualCardSerializer(card, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    elif request.method in ["PUT", "PATCH"]:
        partial = request.method == "PATCH"
        serializer = VirtualCardSerializer(
            card, data=request.data, partial=partial, context={"request": request}
        )
        if serializer.is_valid():
            serializer.save()

            # Create notification for updating a card.
            Notification.objects.create(
                user=request.user,
                notification_type="Updated Credit Card",  # Choose a suitable type for an update.
                amount=0,
            )

            # Send email notification.
            subject = "Virtual Card Updated"
            message = f"Dear {request.user.first_name or request.user.email},\n\nYour virtual card ending with {card.masked_number[-4:]} has been updated successfully."
            html_message = render_to_string(
                "emails/virtual_card_updated.html",
                {
                    "user": request.user,
                    "card": card,
                },
            )
            send_mail(
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [request.user.email],
                html_message=html_message,
            )
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    elif request.method == "DELETE":
        masked_last4 = card.masked_number[-4:]
        card.delete()

        Notification.objects.create(
            user=request.user, notification_type="Deleted Credit Card", amount=0
        )

        # Send email notification.
        subject = "Virtual Card Deleted"
        message = f"Dear {request.user.first_name or request.user.email},\n\nYour virtual card ending with {masked_last4} has been deleted."
        html_message = render_to_string(
            "emails/virtual_card_deleted.html",
            {
                "user": request.user,
                "masked_last4": masked_last4,
            },
        )
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [request.user.email],
            html_message=html_message,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------
# Payment Transaction API Endpoints
# ---------------------------------------------------------------------


@api_view(["GET"])
def payment_transaction_list(request):
    transactions = PaymentTransaction.objects.all()
    serializer = PaymentTransactionSerializer(transactions, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def payment_transaction_detail(request, pk):
    try:
        transaction = PaymentTransaction.objects.get(pk=pk)
    except PaymentTransaction.DoesNotExist:
        return Response(
            {"error": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND
        )
    serializer = PaymentTransactionSerializer(transaction)
    return Response(serializer.data)


# ---------------------------------------------------------------------
# NFC Device API Endpoints
# ---------------------------------------------------------------------


@api_view(["GET"])
def nfcdevice_list(request):
    devices = NFCDevice.objects.all()
    serializer = NFCDeviceSerializer(devices, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def nfcdevice_detail(request, pk):
    try:
        device = NFCDevice.objects.get(pk=pk)
    except NFCDevice.DoesNotExist:
        return Response(
            {"error": "NFC Device not found"}, status=status.HTTP_404_NOT_FOUND
        )
    serializer = NFCDeviceSerializer(device)
    return Response(serializer.data)


# ---------------------------------------------------------------------
# Payment Token API Endpoints
# ---------------------------------------------------------------------
@api_view(["GET"])
def paymenttoken_list(request):
    tokens = PaymentToken.objects.all()
    serializer = PaymentTokenSerializer(tokens, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def paymenttoken_detail(request, pk):
    try:
        token = PaymentToken.objects.get(pk=pk)
    except PaymentToken.DoesNotExist:
        return Response(
            {"error": "Payment Token not found"}, status=status.HTTP_404_NOT_FOUND
        )
    serializer = PaymentTokenSerializer(token)
    return Response(serializer.data)


# ---------------------------------------------------------------------
# Notification API Endpoint
# ---------------------------------------------------------------------
@api_view(["GET"])
def notification_list(request):
    notifications = Notification.objects.all()
    serializer = NotificationSerializer(notifications, many=True)
    return Response(serializer.data)


@api_view(["GET"])
def notification_detail(request, pk):
    try:
        notification = Notification.objects.get(pk=pk)
    except Notification.DoesNotExist:
        return Response(
            {"error": "Notification not found"}, status=status.HTTP_404_NOT_FOUND
        )
    serializer = NotificationSerializer(notification)
    return Response(serializer.data)


# ---------------------------------------------------------------------
# SEARCH API Endpoints
# ---------------------------------------------------------------------


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def search_account(request):
    """
    POST { "query": "..." }
    → If query provided: search by exact account_number, user.username, or kyc.First_name
       and only include accounts with kyc_confirmed=True.
    → If query is empty: return all user accounts with kyc_confirmed=True.

    GET
    → Return all user accounts with kyc_confirmed=True.
    """

    base_filter = Q(kyc_confirmed=True)

    if request.method == "POST":
        q = request.data.get("query", "").strip()

        if q:
            match_filter = (
                Q(account_number__iexact=q)
                | Q(user__username__iexact=q)
                | Q(kyc__First_name__iexact=q)
            )
            qs = Account.objects.filter(base_filter & match_filter).distinct()
        else:
            qs = Account.objects.filter(base_filter).distinct()

    elif request.method == "GET":
        qs = Account.objects.filter(base_filter).distinct()

    if not qs.exists():
        return Response(
            {"detail": "No matching accounts found."}, status=status.HTTP_404_NOT_FOUND
        )

    serializer = AccountSearchSerializer(qs, many=True, context={"request": request})
    return Response(serializer.data, status=status.HTTP_200_OK)


# ---------------------------------------------------------------------
# TRANSFER API Endpoints
# ---------------------------------------------------------------------


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def initiate_transfer(request):
    """
    POST { account_number, amount, description? } → creates TX with status="processing"
    """
    serializer = InitiateTransferSerializer(
        data=request.data, context={"request": request}
    )
    serializer.is_valid(raise_exception=True)
    tx = serializer.save()
    return Response(TransactionSerializer(tx).data, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def transaction_detail(request, tx_id):
    """
    GET /api/transactions/{tx_id}/
    """
    try:
        tx = Transaction.objects.get(transaction_id=tx_id, user=request.user)
    except Transaction.DoesNotExist:
        return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
    return Response(TransactionSerializer(tx).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def confirm_transfer(request, tx_id):
    """
    POST /api/transactions/{tx_id}/confirm/ { pin_number }
    """
    try:
        tx = Transaction.objects.get(transaction_id=tx_id, user=request.user)
    except Transaction.DoesNotExist:
        return Response(
            {"detail": "Transaction not found."}, status=status.HTTP_404_NOT_FOUND
        )

    serializer = ConfirmTransferSerializer(
        data=request.data, context={"request": request, "transaction": tx}
    )
    serializer.is_valid(raise_exception=True)
    tx = serializer.save()
    return Response(TransactionSerializer(tx).data)




def get_clickpesa_token():
    response = requests.post(
        "https://api.clickpesa.com/third-parties/generate-token",
        headers={
            "client-id": settings.CLICKPESA_CLIENT_ID,
            "api-key": settings.CLICKPESA_API_KEY,
        },
    )
    if response.status_code == 200:
        return response.json().get("token")
    raise Exception("Failed to authenticate with ClickPesa")



@api_view(["POST"])
@permission_classes([IsAuthenticated])
def topup_view(request):
    amount = request.data.get("amount")
    phone = request.data.get("phone")

    if not amount or not phone:
        return Response({"error": "Amount and phone are required."}, status=400)

    account = Account.objects.get(user=request.user)
    order_ref = "BLU" + get_random_string(10).upper()

    try:
        token = get_clickpesa_token()

        # Preview
        preview = requests.post(
            "https://api.clickpesa.com/third-parties/payments/preview-ussd-push-request",
            json={"amount": str(amount), "currency": "TZS", "orderReference": order_ref},
            headers={"Authorization": token}
        )
        if preview.status_code != 200:
            return Response({"error": "Preview failed"}, status=500)

        # Initiate USSD Push
        push = requests.post(
            "https://api.clickpesa.com/third-parties/payments/initiate-ussd-push-request",
            json={
                "amount": str(amount),
                "currency": "TZS",
                "orderReference": order_ref,
                "phoneNumber": phone
            },
            headers={"Authorization": token}
        )
        if push.status_code != 200:
            return Response({"error": "Push failed"}, status=500)

        # Log pending transaction
        Transaction.objects.create(
            user=request.user,
            amount=amount,
            description=f"Top-up via ClickPesa | OrderRef: {order_ref}",
            reciver=request.user,
            reciver_account=account,
            status="pending",
            transaction_type="recieved",
            reference=order_ref  # Add this field to track
        )

        return Response({"message": "USSD push initiated", "orderReference": order_ref, "CLickpesatoken": token})

    except Exception as e:
        return Response({"error": str(e)}, status=500)



from django.views.decorators.csrf import csrf_exempt

@csrf_exempt
@api_view(["POST"])
def clickpesa_webhook(request):
    data = request.data
    order_ref = data.get("orderReference")
    status_code = data.get("status")

    if not order_ref or not status_code:
        return Response({"error": "Invalid payload"}, status=400)

    try:
        transaction = Transaction.objects.get(reference=order_ref)
        user = transaction.reciver  # or transaction.user

        if status_code in ["SUCCESS", "SETTLED"]:
            transaction.status = "completed"
            transaction.reciver_account.account_balance += transaction.amount
            transaction.reciver_account.save()

            # Send success email
            html_content = render_to_string("emails/topup_success.html", {
                "user": user,
                "amount": transaction.amount,
                "order_reference": order_ref,
                "new_balance": transaction.reciver_account.account_balance,
                "date": now().strftime("%Y-%m-%d %H:%M"),
            })

            email = EmailMultiAlternatives(
                subject="BluPay Top-Up Successful",
                body="Your top-up was successful.",
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[user.email],
            )
            email.attach_alternative(html_content, "text/html")
            email.send(fail_silently=True)
        else:
            transaction.status = "failed"

        transaction.save()
        return Response({"message": "Webhook processed"}, status=200)

    except Transaction.DoesNotExist:
        return Response({"error": "Transaction not found"}, status=404)



def generate_checksum(payload: dict, checksum_key: str):
    # Step 1: Sort payload keys
    sorted_payload = {k: payload[k] for k in sorted(payload)}

    # Step 2: Concatenate values into a string
    payload_string = "".join(str(value) for value in sorted_payload.values())

    # Step 3: HMAC-SHA256 hash
    return hmac.new(checksum_key.encode(), payload_string.encode(), hashlib.sha256).hexdigest()


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def mobile_money_payout_view(request):
    amount = request.data.get("amount")
    phone = request.data.get("phone")

    if not amount or not phone:
        return Response({"error": "Amount and phone are required."}, status=400)

    user = request.user
    account = Account.objects.get(user=user)

    if account.account_balance < float(amount):
        return Response({"error": "Insufficient funds"}, status=400)

    order_ref = "BLUPAY-WD-" + get_random_string(10).upper()
    payout_payload = {
        "amount": str(amount),
        "phoneNumber": phone,
        "currency": "TZS",
        "orderReference": order_ref
    }

    # Add checksum
    # Generate checksum using the correct method
    checksum = generate_checksum(payout_payload, settings.CLICKPESA_API_KEY)
    payout_payload["checksum"] = checksum

    try:
        token = get_clickpesa_token()

        # Preview
        preview = requests.post(
            "https://api.clickpesa.com/third-parties/payouts/preview-mobile-money-payout",
            json=payout_payload,
            headers={"Authorization": token}
        )
        if preview.status_code != 200:
            return Response({"error": "Payout preview failed"}, status=500)

        # Create Payout
        payout = requests.post(
            "https://api.clickpesa.com/third-parties/payouts/create-mobile-money-payout",
            json=payout_payload,
            headers={"Authorization": token}
        )
        if payout.status_code != 200:
            return Response({"error": "Payout request failed"}, status=500)

        # Deduct balance & save transaction
        account.account_balance -= float(amount)
        account.save()

        Transaction.objects.create(
            user=user,
            amount=amount,
            description=f"Withdrawal to MNO via ClickPesa",
            status="pending",
            transaction_type="sent",
            reference=order_ref
        )

        return Response({"message": "Payout initiated", "orderReference": order_ref})

    except Exception as e:
        return Response({"error": str(e)}, status=500)





@api_view(["GET"])
@permission_classes([IsAuthenticated])
def query_payout_status(request, order_reference):
    try:
        # Get user token from ClickPesa
        token_response = requests.post(
            "https://api.clickpesa.com/third-parties/generate-token",
            headers={
                "client-id": settings.CLICKPESA_CLIENT_ID,
                "api-key": settings.CLICKPESA_API_KEY
            }
        )
        token_data = token_response.json()
        token = token_data.get("token")

        if not token:
            return Response({"error": "Failed to get token from ClickPesa"}, status=500)

        # Query payout status
        status_response = requests.get(
            f"https://api.clickpesa.com/third-parties/payouts/{order_reference}",
            headers={"Authorization": f"Bearer {token}"}
        )

        if status_response.status_code != 200:
            return Response({"error": "Failed to fetch payout status"}, status=500)

        payout_data = status_response.json()
        status = payout_data.get("status")
        channel_provider = payout_data.get("channelProvider")

        # Update local Transaction
        transaction = Transaction.objects.get(reference=order_reference)
        transaction.status = status.lower()
        transaction.description += f" | via {channel_provider}"
        transaction.save()

        # Send success email if status is SUCCESS
        if status == "SUCCESS":
            send_mail(
                subject="Payout Successful",
                message=f"Dear {transaction.user.username},\n\nYour payout of {transaction.amount} TZS to {channel_provider} was successful.\n\nOrder Ref: {order_reference}",
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[transaction.user.email],
                fail_silently=False,
            )

        return Response({
            "orderReference": payout_data["orderReference"],
            "amount": payout_data["amount"],
            "currency": payout_data["currency"],
            "status": payout_data["status"],
            "channel": payout_data["channel"],
            "channelProvider": payout_data["channelProvider"],
            "fee": payout_data["fee"],
            "createdAt": payout_data["createdAt"],
            "updatedAt": payout_data["updatedAt"],
        })

    except Transaction.DoesNotExist:
        return Response({"error": "Transaction not found"}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)