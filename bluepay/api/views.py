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
    MobileMoneyProviderSerializer,
    PaymentStatusHistorySerializer,
    PaymentSerializer,
    PaymentStatusQuerySerializer,
    InitiateMobileMoneyPaymentSerializer,
    PaymentSummarySerializer,
    BulkPaymentStatusSerializer,
    TopupRequestSerializer,
    TopupResponseSerializer,
    PayoutStatusHistorySerializer,
    PayoutSerializer,
    PayoutRequestSerializer,
    PayoutPreviewSerializer,
    PayoutSummarySerializer






)
from django.utils.crypto import get_random_string
import requests
import pycountry
from .utils import validate_phone_number, validate_tanzanian_phone, generate_transaction_reference, mask_sensitive_data, get_available_payment_methods
import uuid
from django.conf import settings
from django.db import transaction as db_transaction
from django.utils import timezone
from datetime import datetime, timedelta
import logging
import re
from django.db import models
from django.views.decorators.csrf import csrf_exempt



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







@api_view(["GET"])
@permission_classes([IsAuthenticated])
def transaction_history(request):
    """
    GET /api/transactions/history/

    Returns transactions where the authenticated user is either sender or receiver.
    Optional filters:
        - type: 'credit' or 'debit'
        - status: 'pending', 'success', 'failed'
        - start_date: YYYY-MM-DD
        - end_date: YYYY-MM-DD
    """
    user = request.user

    # Get transactions where the user is sender OR receiver
    qs = Transaction.objects.filter(
        Q(sender=user) | Q(reciver=user)
    )

    # Filter by transaction type
    tx_type = request.query_params.get("type")
    if tx_type in ["credit", "debit"]:
        qs = qs.filter(transaction_type=tx_type)

    # Filter by status
    status_param = request.query_params.get("status")
    if status_param:
        qs = qs.filter(status=status_param)

    # Date filtering
    start_date = request.query_params.get("start_date")
    if start_date:
        qs = qs.filter(date__date__gte=start_date)

    end_date = request.query_params.get("end_date")
    if end_date:
        qs = qs.filter(date__date__lte=end_date)

    # Order by most recent
    qs = qs.order_by("-date")

    return Response(TransactionSerializer(qs, many=True).data, status=status.HTTP_200_OK)



# -----------------------------------------------------------------------------
# Top-up API Endpoints
# -----------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_topup(request):
    """
    Initiate a top-up transaction using ClickPesa USSD push
    """
    # Validate input data
    serializer = TopupRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    validated_data = serializer.validated_data
    amount = validated_data['amount']
    phone = validated_data['phone']

    try:
        # Get user account
        account = get_object_or_404(Account, user=request.user)
        
        # Check if account is active
        if account.account_status != 'active':
            return Response(
                {"error": "Account must be active to perform top-ups"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check transaction limits
        if amount > account.single_transaction_limit:
            return Response(
                {
                    "error": f"Amount exceeds single transaction limit of {account.single_transaction_limit} TZS",
                    "limit": account.single_transaction_limit
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check daily limit
        today = timezone.now().date()
        daily_usage = Transaction.objects.filter(
            reciver_account=account,
            transaction_type='recieved',
            status='completed',
            date__date=today
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
        
        if daily_usage + amount > account.daily_limit:
            return Response(
                {
                    "error": f"Amount exceeds daily limit. Used: {daily_usage} TZS, Limit: {account.daily_limit} TZS",
                    "daily_used": daily_usage,
                    "daily_limit": account.daily_limit,
                    "remaining": account.daily_limit - daily_usage
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check KYC requirements for large amounts
        if amount > 50000 and not account.kyc_confirmed:
            return Response(
                {"error": "KYC verification required for amounts above 50,000 TZS"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate unique order reference
        order_ref = generate_transaction_reference("BLU")
        
        # Create payment record using atomic transaction
        with db_transaction.atomic():
            # Create Payment record
            payment = Payment.objects.create(
                payment_reference=f"PAY_{order_ref}",
                order_reference=order_ref,
                account=account,
                transaction_type='DEPOSIT',
                payment_method='MOBILE_MONEY',
                amount=amount,
                currency='TZS',
                customer_name=request.user.get_full_name() or request.user.email,
                customer_phone=phone,
                customer_email=request.user.email,
                status='PENDING',
                phone_number=phone,
                ussd_push_initiated=False,
                message="Payment initiated"
            )
            
            # Create legacy Transaction record for backward compatibility
            transaction_record = Transaction.objects.create(
                user=request.user,
                amount=amount,
                description=f"Top-up via ClickPesa | OrderRef: {order_ref}",
                reciver=request.user,
                reciver_account=account,
                status="pending",
                transaction_type="recieved",
                reference=order_ref,
                payment=payment
            )
            
            # Initiate ClickPesa payment
            success, result_data = payment.initiate_clickpesa_payment()
            
            if not success:
                logger.error(f"ClickPesa payment initiation failed for {order_ref}: {result_data}")
                return Response(
                    {"error": "Payment initiation failed", "details": result_data},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Create payment status history
            PaymentStatusHistory.objects.create(
                payment=payment,
                previous_status=None,
                new_status=payment.status,
                message="USSD push initiated successfully"
            )
        
        # Prepare response
        response_data = {
            "message": "USSD push initiated successfully. Please check your phone for the payment prompt.",
            "order_reference": order_ref,
            "amount": str(amount),
            "phone": phone,
            "status": payment.status,
            "channel": payment.metadata.get('channel'),
            "transaction_id": payment.clickpesa_transaction_id,
            "instructions": "You will receive a USSD prompt on your phone. Follow the instructions to complete the payment."
        }
        
        logger.info(f"Top-up initiated successfully: {order_ref} for user {request.user.email}")
        return Response(response_data, status=status.HTTP_201_CREATED)
        
    except Account.DoesNotExist:
        return Response(
            {"error": "Account not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Unexpected error in topup initiation: {e}")
        return Response(
            {"error": "Internal server error", "details": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_payment_methods(request):
    """
    Check available payment methods for a given amount
    """
    amount = request.GET.get('amount')
    if not amount:
        return Response(
            {"error": "Amount parameter is required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        amount = Decimal(amount)
        if amount < 1000:
            return Response(
                {"error": "Minimum amount is 1,000 TZS"},
                status=status.HTTP_400_BAD_REQUEST
            )
    except (ValueError, TypeError):
        return Response(
            {"error": "Invalid amount format"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    methods_data = get_available_payment_methods(amount, "TZS")
    return Response(methods_data, status=status.HTTP_200_OK)



@api_view(['GET'])
@permission_classes([IsAuthenticated])
def topup_status(request, order_reference):
    """
    Check the status of a specific top-up transaction
    """
    try:
        # Get payment from database
        payment = Payment.objects.get(
            order_reference=order_reference,
            account__user=request.user
        )
        
        # Query ClickPesa for latest status
        success, api_data = payment.query_clickpesa_status()
        
        # Serialize payment data
        serializer = PaymentSerializer(payment, context={'request': request})
        
        response_data = {
            "payment": serializer.data,
            "api_data": api_data if success else None,
            "updated_from_api": success
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Payment.DoesNotExist:
        return Response(
            {"error": "Payment not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error checking payment status: {e}")
        return Response(
            {"error": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def topup_history(request):
    """
    Get user's top-up transaction history
    """
    account = get_object_or_404(Account, user=request.user)
    
    # Get query parameters
    page = int(request.GET.get('page', 1))
    page_size = min(int(request.GET.get('page_size', 20)), 100)
    status_filter = request.GET.get('status')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Base query for top-up payments
    payments = Payment.objects.filter(
        account=account,
        transaction_type='DEPOSIT'
    ).order_by('-created_at')
    
    # Apply filters
    if status_filter:
        payments = payments.filter(status=status_filter.upper())
    
    if start_date:
        try:
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            payments = payments.filter(created_at__gte=start_date)
        except ValueError:
            return Response(
                {"error": "Invalid start_date format. Use ISO format."},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    if end_date:
        try:
            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            payments = payments.filter(created_at__lte=end_date)
        except ValueError:
            return Response(
                {"error": "Invalid end_date format. Use ISO format."},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    # Pagination
    total_count = payments.count()
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    payments = payments[start_idx:end_idx]
    
    # Serialize data
    serializer = PaymentSerializer(payments, many=True, context={'request': request})
    
    # Calculate statistics
    stats = Payment.objects.filter(
        account=account,
        transaction_type='DEPOSIT'
    ).aggregate(
        total_amount=models.Sum('amount'),
        successful_amount=models.Sum('collected_amount', filter=models.Q(status__in=['SUCCESS', 'SETTLED'])),
        total_count=models.Count('id'),
        successful_count=models.Count('id', filter=models.Q(status__in=['SUCCESS', 'SETTLED']))
    )
    
    return Response({
        "count": total_count,
        "page": page,
        "page_size": page_size,
        "results": serializer.data,
        "statistics": {
            "total_amount": stats['total_amount'] or 0,
            "successful_amount": stats['successful_amount'] or 0,
            "total_transactions": stats['total_count'] or 0,
            "successful_transactions": stats['successful_count'] or 0,
            "success_rate": round(
                (stats['successful_count'] / stats['total_count'] * 100) 
                if stats['total_count'] > 0 else 0, 2
            )
        }
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def topup_limits(request):
    """
    Get top-up limits and current usage for the user
    """
    account = get_object_or_404(Account, user=request.user)
    
    # Calculate current usage
    today = timezone.now().date()
    current_month = timezone.now().replace(day=1).date()
    
    daily_used = Transaction.objects.filter(
        reciver_account=account,
        transaction_type='recieved',
        status='completed',
        date__date=today
    ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
    
    monthly_used = Transaction.objects.filter(
        reciver_account=account,
        transaction_type='recieved',
        status='completed',
        date__date__gte=current_month
    ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
    
    return Response({
        "limits": {
            "daily_limit": account.daily_limit,
            "monthly_limit": account.monthly_limit,
            "single_transaction_limit": account.single_transaction_limit,
            "minimum_amount": 1000
        },
        "usage": {
            "daily_used": daily_used,
            "monthly_used": monthly_used,
            "daily_remaining": max(Decimal('0'), account.daily_limit - daily_used),
            "monthly_remaining": max(Decimal('0'), account.monthly_limit - monthly_used)
        },
        "kyc_status": {
            "kyc_submitted": account.kyc_submitted,
            "kyc_confirmed": account.kyc_confirmed,
            "account_status": account.account_status
        },
        "payment_methods_info": {
            "supported_operators": ["M-PESA", "TIGO-PESA", "AIRTEL-MONEY"],
            "currency": "TZS",
            "processing_time": "Instant to 5 minutes"
        }
    }, status=status.HTTP_200_OK)

@csrf_exempt
@api_view(["POST"])
def clickpesa_webhook(request):
    """
    Enhanced webhook handler for ClickPesa payment notifications
    """
    try:
        data = request.data
        order_ref = data.get("orderReference")
        status_code = data.get("status")
        
        # Log the webhook data (masked for security)
        masked_data = mask_sensitive_data(data)
        logger.info(f"Received ClickPesa webhook: {masked_data}")
        
        # Validate required fields
        if not order_ref or not status_code:
            logger.warning(f"Invalid webhook payload: missing orderReference or status")
            return Response(
                {"error": "Invalid payload - missing orderReference or status"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Store webhook data first
        webhook = PaymentWebhook.objects.create(
            order_reference=order_ref,
            webhook_data=data
        )
        
        # Process the webhook
        with db_transaction.atomic():
            try:
                # Get payment record
                payment = Payment.objects.select_for_update().get(order_reference=order_ref)
                webhook.payment = payment
                webhook.save()
                
                # Get legacy transaction record
                try:
                    transaction_record = Transaction.objects.select_for_update().get(reference=order_ref)
                except Transaction.DoesNotExist:
                    # Create transaction record if it doesn't exist
                    transaction_record = Transaction.objects.create(
                        user=payment.account.user,
                        amount=payment.amount,
                        description=f"Top-up via ClickPesa | OrderRef: {order_ref}",
                        reciver=payment.account.user,
                        reciver_account=payment.account,
                        status="pending",
                        transaction_type="recieved",
                        reference=order_ref,
                        payment=payment
                    )
                
                old_status = payment.status
                user = payment.account.user
                
                # Update payment and transaction based on status
                if status_code in ["SUCCESS", "SETTLED"]:
                    # Update payment
                    payment.status = "SUCCESS"
                    payment.collected_amount = data.get("collectedAmount", payment.amount)
                    payment.collected_currency = data.get("collectedCurrency", "TZS")
                    payment.message = data.get("message", "Payment completed successfully")
                    payment.clickpesa_updated_at = timezone.now()
                    
                    # Update customer info if provided
                    if "customer" in data:
                        customer = data["customer"]
                        if "customerName" in customer:
                            payment.customer_name = customer["customerName"]
                        if "customerPhoneNumber" in customer:
                            payment.customer_phone = customer["customerPhoneNumber"]
                        if "customerEmail" in customer:
                            payment.customer_email = customer["customerEmail"]
                    
                    payment.save()
                    
                    # Update legacy transaction
                    transaction_record.status = "completed"
                    transaction_record.save()
                    
                    # Update account balance
                    collected_amount = payment.collected_amount or payment.amount
                    payment.account.account_balance += collected_amount
                    payment.account.save()
                    
                    # Create status history
                    PaymentStatusHistory.objects.create(
                        payment=payment,
                        previous_status=old_status,
                        new_status="SUCCESS",
                        message=f"Payment completed via webhook. Amount: {collected_amount} {payment.collected_currency or payment.currency}"
                    )
                    
                    # Send success email
                    try:
                        _send_topup_success_email(user, payment, collected_amount)
                        logger.info(f"Success email sent for topup {order_ref}")
                    except Exception as email_error:
                        logger.error(f"Failed to send success email for {order_ref}: {email_error}")
                    
                elif status_code == "FAILED":
                    # Update payment
                    payment.status = "FAILED"
                    payment.message = data.get("message", "Payment failed")
                    payment.clickpesa_updated_at = timezone.now()
                    payment.save()
                    
                    # Update legacy transaction
                    transaction_record.status = "failed"
                    transaction_record.save()
                    
                    # Create status history
                    PaymentStatusHistory.objects.create(
                        payment=payment,
                        previous_status=old_status,
                        new_status="FAILED",
                        message=f"Payment failed via webhook: {data.get('message', 'Unknown error')}"
                    )
                    
                    # Send failure email
                    try:
                        _send_topup_failure_email(user, payment)
                        logger.info(f"Failure email sent for topup {order_ref}")
                    except Exception as email_error:
                        logger.error(f"Failed to send failure email for {order_ref}: {email_error}")
                
                else:
                    # Handle other statuses (PROCESSING, PENDING, etc.)
                    payment.status = status_code
                    payment.message = data.get("message", f"Payment status: {status_code}")
                    payment.clickpesa_updated_at = timezone.now()
                    payment.save()
                    
                    # Update legacy transaction
                    if status_code in ["PROCESSING", "PENDING"]:
                        transaction_record.status = "pending"
                    else:
                        transaction_record.status = status_code.lower()
                    transaction_record.save()
                    
                    # Create status history
                    PaymentStatusHistory.objects.create(
                        payment=payment,
                        previous_status=old_status,
                        new_status=status_code,
                        message=f"Status updated via webhook: {data.get('message', '')}"
                    )
                
                # Mark webhook as processed
                webhook.processed = True
                webhook.save()
                
                logger.info(f"Webhook processed successfully for {order_ref}: {old_status} -> {payment.status}")
                
            except Payment.DoesNotExist:
                logger.warning(f"Webhook received for unknown payment: {order_ref}")
                return Response(
                    {"error": "Payment not found", "order_reference": order_ref},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        return Response(
            {"message": "Webhook processed successfully", "order_reference": order_ref},
            status=status.HTTP_200_OK
        )
        
    except Exception as e:
        logger.error(f"Error processing webhook: {e}")
        return Response(
            {"error": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

def _send_topup_success_email(user, payment, amount):
    """Send success email for completed top-up"""
    try:
        subject = "BluPay Top-Up Successful"
        html_content = render_to_string("emails/topup_success.html", {
            "user": user,
            "amount": amount,
            "currency": payment.collected_currency or payment.currency,
            "order_reference": payment.order_reference,
            "new_balance": payment.account.account_balance,
            "date": timezone.now().strftime("%Y-%m-%d %H:%M"),
            "phone": payment.phone_number,
            "channel": payment.metadata.get('channel', 'Mobile Money'),
        })
        
        email = EmailMultiAlternatives(
            subject=subject,
            body="Your top-up was successful.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=True)
        
    except Exception as e:
        logger.error(f"Failed to send success email: {e}")

def _send_topup_failure_email(user, payment):
    """Send failure email for failed top-up"""
    try:
        subject = "BluPay Top-Up Failed"
        html_content = render_to_string("emails/topup_failed.html", {
            "user": user,
            "amount": payment.amount,
            "currency": payment.currency,
            "order_reference": payment.order_reference,
            "reason": payment.message or "Payment processing failed",
            "date": timezone.now().strftime("%Y-%m-%d %H:%M"),
        })
        
        email = EmailMultiAlternatives(
            subject=subject,
            body="Your top-up attempt failed.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=True)
        
    except Exception as e:
        logger.error(f"Failed to send failure email: {e}")




# -----------------------------------------------------------------------------
# Payout API Endpoints
# -----------------------------------------------------------------------------

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def initiate_payout(request):
    """
    Initiate a payout transaction using ClickPesa mobile money
    """
    # Validate input data
    serializer = PayoutRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    validated_data = serializer.validated_data
    amount = validated_data['amount']
    phone = validated_data['phone']
    beneficiary_name = validated_data.get('beneficiary_name', 'Beneficiary')

    try:
        # Get user account
        account = get_object_or_404(Account, user=request.user)
        
        # Check if account is active
        if account.account_status != 'active':
            return Response(
                {"error": "Account must be active to perform payouts"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check KYC requirements
        if not account.kyc_confirmed:
            return Response(
                {"error": "KYC verification required for payouts"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check transaction limits
        if amount > account.single_transaction_limit:
            return Response(
                {
                    "error": f"Amount exceeds single transaction limit of {account.single_transaction_limit} TZS",
                    "limit": account.single_transaction_limit
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check daily limit for payouts
        today = timezone.now().date()
        daily_payout_usage = Payout.objects.filter(
            account=account,
            status='SUCCESS',
            created_at__date=today
        ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
        
        if daily_payout_usage + amount > account.daily_limit:
            return Response(
                {
                    "error": f"Amount exceeds daily payout limit. Used: {daily_payout_usage} TZS, Limit: {account.daily_limit} TZS",
                    "daily_used": daily_payout_usage,
                    "daily_limit": account.daily_limit,
                    "remaining": account.daily_limit - daily_payout_usage
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate unique order reference
        order_ref = generate_transaction_reference("PAYOUT")
        
        # Create payout record using atomic transaction
        with db_transaction.atomic():
            # Create Payout record
            payout = Payout.objects.create(
                payout_reference=f"PAYOUT_{order_ref}",
                order_reference=order_ref,
                account=account,
                payout_type='WITHDRAWAL',
                channel='MOBILE_MONEY',
                amount=amount,
                currency='TZS',
                total_amount=amount,  # Will be updated after preview
                beneficiary_name=beneficiary_name,
                beneficiary_phone=phone,
                beneficiary_email=request.user.email,
                status='PENDING',
                message="Payout initiated"
            )
            
            # Initiate ClickPesa payout
            success, result_data = payout.initiate_clickpesa_payout()
            
            if not success:
                logger.error(f"ClickPesa payout initiation failed for {order_ref}: {result_data}")
                return Response(
                    {"error": "Payout initiation failed", "details": result_data},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
            
            # Create payout status history
            PayoutStatusHistory.objects.create(
                payout=payout,
                previous_status=None,
                new_status=payout.status,
                message="Payout initiated successfully"
            )
            
            # Create legacy transaction record for tracking
            Transaction.objects.create(
                user=request.user,
                amount=payout.total_amount,
                description=f"Payout to {phone} | OrderRef: {order_ref}",
                reciver=request.user,
                reciver_account=account,
                status="pending",
                transaction_type="sent",
                reference=order_ref
            )
        
        # Prepare response
        response_data = {
            "message": "Payout initiated successfully. Processing withdrawal to mobile money.",
            "order_reference": order_ref,
            "amount": str(amount),
            "fee": str(payout.fee),
            "total_amount": str(payout.total_amount),
            "phone": phone,
            "status": payout.status,
            "channel_provider": payout.channel_provider,
            "beneficiary_name": beneficiary_name,
            "estimated_completion": "5-15 minutes"
        }
        
        logger.info(f"Payout initiated successfully: {order_ref} for user {request.user.email}")
        return Response(response_data, status=status.HTTP_201_CREATED)
        
    except Account.DoesNotExist:
        return Response(
            {"error": "Account not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Unexpected error in payout initiation: {e}")
        return Response(
            {"error": "Internal server error", "details": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def preview_payout(request):
    """
    Preview payout to get fees and channel information
    """
    # Validate input data
    serializer = PayoutRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    validated_data = serializer.validated_data
    amount = validated_data['amount']
    phone = validated_data['phone']

    try:
        # Get user account
        account = get_object_or_404(Account, user=request.user)
        
        # Check if account is active
        if account.account_status != 'active':
            return Response(
                {"error": "Account must be active to perform payouts"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Generate temporary order reference for preview
        temp_order_ref = generate_transaction_reference("PREVIEW")
        
        # Initialize ClickPesa service
        clickpesa = ClickPesaAPI()
        
        # Preview the payout
        preview_success, preview_data = clickpesa.preview_mobile_money_payout(
            str(amount), phone, "TZS", temp_order_ref
        )
        
        if not preview_success:
            logger.error(f"Payout preview failed for {temp_order_ref}: {preview_data}")
            return Response(
                {"error": "Payout preview failed", "details": preview_data},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        # Calculate total cost
        fee = Decimal(str(preview_data.get('fee', 0)))
        total_amount = amount + fee
        
        # Check if user has sufficient balance
        sufficient_balance = account.account_balance >= total_amount
        
        response_data = {
            "amount": str(amount),
            "fee": str(fee),
            "total_amount": str(total_amount),
            "currency": "TZS",
            "channel_provider": preview_data.get('channelProvider', ''),
            "payout_fee_bearer": preview_data.get('payoutFeeBearer', 'customer'),
            "account_balance": str(account.account_balance),
            "sufficient_balance": sufficient_balance,
            "phone": phone,
            "estimated_completion": "5-15 minutes"
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Account.DoesNotExist:
        return Response(
            {"error": "Account not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Unexpected error in payout preview: {e}")
        return Response(
            {"error": "Internal server error", "details": str(e)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payout_status(request, order_reference):
    """
    Check the status of a specific payout transaction
    """
    try:
        # Get payout from database
        payout = Payout.objects.get(
            order_reference=order_reference,
            account__user=request.user
        )
        
        # Query ClickPesa for latest status
        success, api_data = payout.query_clickpesa_status()
        
        # Serialize payout data
        serializer = PayoutSerializer(payout, context={'request': request})
        
        response_data = {
            "payout": serializer.data,
            "api_data": api_data if success else None,
            "updated_from_api": success
        }
        
        return Response(response_data, status=status.HTTP_200_OK)
        
    except Payout.DoesNotExist:
        return Response(
            {"error": "Payout not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    except Exception as e:
        logger.error(f"Error checking payout status: {e}")
        return Response(
            {"error": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payout_history(request):
    """
    Get user's payout transaction history
    """
    account = get_object_or_404(Account, user=request.user)
    
    # Get query parameters
    page = int(request.GET.get('page', 1))
    page_size = min(int(request.GET.get('page_size', 20)), 100)
    status_filter = request.GET.get('status')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Base query for payouts
    payouts = Payout.objects.filter(account=account).order_by('-created_at')
    
    # Apply filters
    if status_filter:
        payouts = payouts.filter(status=status_filter.upper())
    
    if start_date:
        try:
            start_date = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            payouts = payouts.filter(created_at__gte=start_date)
        except ValueError:
            return Response(
                {"error": "Invalid start_date format. Use ISO format."},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    if end_date:
        try:
            end_date = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            payouts = payouts.filter(created_at__lte=end_date)
        except ValueError:
            return Response(
                {"error": "Invalid end_date format. Use ISO format."},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    # Pagination
    total_count = payouts.count()
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    payouts = payouts[start_idx:end_idx]
    
    # Serialize data
    serializer = PayoutSerializer(payouts, many=True, context={'request': request})
    
    # Calculate statistics
    stats = Payout.objects.filter(account=account).aggregate(
        total_amount=models.Sum('amount'),
        successful_amount=models.Sum('amount', filter=models.Q(status='SUCCESS')),
        total_fees=models.Sum('fee'),
        total_count=models.Count('id'),
        successful_count=models.Count('id', filter=models.Q(status='SUCCESS'))
    )
    
    return Response({
        "count": total_count,
        "page": page,
        "page_size": page_size,
        "results": serializer.data,
        "statistics": {
            "total_amount": stats['total_amount'] or 0,
            "successful_amount": stats['successful_amount'] or 0,
            "total_fees": stats['total_fees'] or 0,
            "total_transactions": stats['total_count'] or 0,
            "successful_transactions": stats['successful_count'] or 0,
            "success_rate": round(
                (stats['successful_count'] / stats['total_count'] * 100) 
                if stats['total_count'] > 0 else 0, 2
            )
        }
    }, status=status.HTTP_200_OK)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def payout_limits(request):
    """
    Get payout limits and current usage for the user
    """
    account = get_object_or_404(Account, user=request.user)
    
    # Calculate current usage
    today = timezone.now().date()
    current_month = timezone.now().replace(day=1).date()
    
    daily_used = Payout.objects.filter(
        account=account,
        status='SUCCESS',
        created_at__date=today
    ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
    
    monthly_used = Payout.objects.filter(
        account=account,
        status='SUCCESS',
        created_at__date__gte=current_month
    ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
    
    return Response({
        "limits": {
            "daily_limit": account.daily_limit,
            "monthly_limit": account.monthly_limit,
            "single_transaction_limit": account.single_transaction_limit,
            "minimum_amount": 1000,
            "maximum_amount": 5000000
        },
        "usage": {
            "daily_used": daily_used,
            "monthly_used": monthly_used,
            "daily_remaining": max(Decimal('0'), account.daily_limit - daily_used),
            "monthly_remaining": max(Decimal('0'), account.monthly_limit - monthly_used)
        },
        "account_info": {
            "current_balance": account.account_balance,
            "kyc_confirmed": account.kyc_confirmed,
            "account_status": account.account_status
        },
        "payout_info": {
            "supported_operators": ["M-PESA", "TIGO-PESA", "AIRTEL-MONEY"],
            "currency": "TZS",
            "processing_time": "5-15 minutes",
            "fee_bearer": "customer"
        }
    }, status=status.HTTP_200_OK)

@csrf_exempt
@api_view(["POST"])
def clickpesa_payout_webhook(request):
    """
    Enhanced webhook handler for ClickPesa payout notifications
    """
    try:
        data = request.data
        order_ref = data.get("orderReference")
        status_code = data.get("status")
        
        # Log the webhook data (masked for security)
        masked_data = mask_sensitive_data(data)
        logger.info(f"Received ClickPesa payout webhook: {masked_data}")
        
        # Validate required fields
        if not order_ref or not status_code:
            logger.warning(f"Invalid payout webhook payload: missing orderReference or status")
            return Response(
                {"error": "Invalid payload - missing orderReference or status"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Store webhook data first
        webhook = PayoutWebhook.objects.create(
            order_reference=order_ref,
            webhook_data=data
        )
        
        # Process the webhook
        with db_transaction.atomic():
            try:
                # Get payout record
                payout = Payout.objects.select_for_update().get(order_reference=order_ref)
                webhook.payout = payout
                webhook.save()
                
                old_status = payout.status
                user = payout.account.user
                
                # Update payout based on status
                if status_code == "SUCCESS":
                    # Update payout
                    payout.status = "SUCCESS"
                    payout.message = data.get("message", "Payout completed successfully")
                    payout.clickpesa_updated_at = timezone.now()
                    
                    # Update beneficiary info if provided
                    if "beneficiary" in data:
                        beneficiary = data["beneficiary"]
                        if "name" in beneficiary:
                            payout.beneficiary_name = beneficiary["name"]
                        if "phoneNumber" in beneficiary:
                            payout.beneficiary_phone = beneficiary["phoneNumber"]
                    
                    payout.save()
                    
                    # Update legacy transaction
                    try:
                        transaction_record = Transaction.objects.get(reference=order_ref)
                        transaction_record.status = "completed"
                        transaction_record.save()
                    except Transaction.DoesNotExist:
                        pass
                    
                    # Create status history
                    PayoutStatusHistory.objects.create(
                        payout=payout,
                        previous_status=old_status,
                        new_status="SUCCESS",
                        message=f"Payout completed via webhook. Amount: {payout.amount} {payout.currency}"
                    )
                    
                    # Send success email
                    try:
                        _send_payout_success_email(user, payout)
                        logger.info(f"Success email sent for payout {order_ref}")
                    except Exception as email_error:
                        logger.error(f"Failed to send success email for {order_ref}: {email_error}")
                    
                elif status_code in ["FAILED", "REVERSED", "REFUNDED"]:
                    # Update payout
                    payout.status = status_code
                    payout.message = data.get("message", f"Payout {status_code.lower()}")
                    payout.clickpesa_updated_at = timezone.now()
                    payout.save()
                    
                    # Refund the amount to account balance
                    payout.account.account_balance += payout.total_amount
                    payout.account.save()
                    
                    # Update legacy transaction
                    try:
                        transaction_record = Transaction.objects.get(reference=order_ref)
                        transaction_record.status = "failed"
                        transaction_record.save()
                    except Transaction.DoesNotExist:
                        pass
                    
                    # Create status history
                    PayoutStatusHistory.objects.create(
                        payout=payout,
                        previous_status=old_status,
                        new_status=status_code,
                        message=f"Payout {status_code.lower()} via webhook: {data.get('message', 'Unknown error')}"
                    )
                    
                    # Send failure email
                    try:
                        _send_payout_failure_email(user, payout)
                        logger.info(f"Failure email sent for payout {order_ref}")
                    except Exception as email_error:
                        logger.error(f"Failed to send failure email for {order_ref}: {email_error}")
                
                else:
                    # Handle other statuses (PROCESSING, PENDING, AUTHORIZED, etc.)
                    payout.status = status_code
                    payout.message = data.get("message", f"Payout status: {status_code}")
                    payout.clickpesa_updated_at = timezone.now()
                    payout.save()
                    
                    # Create status history
                    PayoutStatusHistory.objects.create(
                        payout=payout,
                        previous_status=old_status,
                        new_status=status_code,
                        message=f"Status updated via webhook: {data.get('message', '')}"
                    )
                
                # Mark webhook as processed
                webhook.processed = True
                webhook.save()
                
                logger.info(f"Payout webhook processed successfully for {order_ref}: {old_status} -> {payout.status}")
                
            except Payout.DoesNotExist:
                logger.warning(f"Payout webhook received for unknown payout: {order_ref}")
                return Response(
                    {"error": "Payout not found", "order_reference": order_ref},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        return Response(
            {"message": "Payout webhook processed successfully", "order_reference": order_ref},
            status=status.HTTP_200_OK
        )
        
    except Exception as e:
        logger.error(f"Error processing payout webhook: {e}")
        return Response(
            {"error": "Internal server error"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )

def _send_payout_success_email(user, payout):
    """Send success email for completed payout"""
    try:
        subject = "BluPay Payout Successful"
        html_content = render_to_string("emails/payout_success.html", {
            "user": user,
            "amount": payout.amount,
            "fee": payout.fee,
            "total_amount": payout.total_amount,
            "currency": payout.currency,
            "order_reference": payout.order_reference,
            "beneficiary_name": payout.beneficiary_name,
            "beneficiary_phone": payout.beneficiary_phone,
            "channel_provider": payout.channel_provider,
            "new_balance": payout.account.account_balance,
            "date": timezone.now().strftime("%Y-%m-%d %H:%M"),
        })
        
        email = EmailMultiAlternatives(
            subject=subject,
            body="Your payout was successful.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=True)
        
    except Exception as e:
        logger.error(f"Failed to send payout success email: {e}")

def _send_payout_failure_email(user, payout):
    """Send failure email for failed payout"""
    try:
        subject = "BluPay Payout Failed"
        html_content = render_to_string("emails/payout_failed.html", {
            "user": user,
            "amount": payout.amount,
            "currency": payout.currency,
            "order_reference": payout.order_reference,
            "beneficiary_phone": payout.beneficiary_phone,
            "reason": payout.message or "Payout processing failed",
            "date": timezone.now().strftime("%Y-%m-%d %H:%M"),
        })
        
        email = EmailMultiAlternatives(
            subject=subject,
            body="Your payout attempt failed.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=True)
        
    except Exception as e:
        logger.error(f"Failed to send payout failure email: {e}")


