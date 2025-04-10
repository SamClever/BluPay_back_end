from django.shortcuts import get_object_or_404
from userAccount.models import User
from userAccount.api.serializer import UserSerializer
from Accounts.api.serializer import AccountSerializer,KYCSerializer
from Accounts.models import Account, KYC
from rest_framework.decorators import api_view,permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated,AllowAny
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string


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
# Dashboard API Endpoint
# -----------------------------------------------------------------------------

def dashboard(request):
    user = request.user
        # Ensure KYC record exists, else inform the client.
    try:
        kyc = KYC.objects.get(user=user)
    except KYC.DoesNotExist:
        return Response(
            {"detail": "You need to submit your KYC."},
            status=status.HTTP_404_NOT_FOUND
        )
    

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
        # "recent_transfer": TransactionSerializer(recent_transfer).data if recent_transfer else None,
        # "recent_received_transfer": TransactionSerializer(recent_received_transfer).data if recent_received_transfer else None,
        # "sender_transactions": TransactionSerializer(sender_transactions, many=True).data,
        # "receiver_transactions": TransactionSerializer(receiver_transactions, many=True).data,
        # "request_sender_transactions": TransactionSerializer(request_sender_transactions, many=True).data,
        # "request_receiver_transactions": TransactionSerializer(request_receiver_transactions, many=True).data,
        # "credit_cards": CreditCardSerializer(credit_cards, many=True).data,
    }
    return Response(data, status=status.HTTP_200_OK)

