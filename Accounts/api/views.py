
from userAccount.models import User
from userAccount.api.serializer import UserSerializer
from Accounts.api.serializer import AccountSerializer, KycSerializer,KYCSerializer
from Accounts.models import Account, KYC
from rest_framework.decorators import api_view,permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated,AllowAny
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string


# Account endpoints
@api_view(['GET'])
def view_account(request):
    accounts = Account.objects.all()
    serializer = AccountSerializer(accounts, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def view_account_id(request, pk):
    try:
        account = Account.objects.get(pk=pk)
    except Account.DoesNotExist:
        return Response({'error': 'Account not found'}, status=status.HTTP_404_NOT_FOUND)
    serializer = AccountSerializer(account)
    return Response(serializer.data)




# KYC endpoints
# @api_view(['GET'])
# def view_kyc(request):
#     kyc_records = KYC.objects.all()
#     serializer = KycSerializer(kyc_records, many=True)
#     return Response(serializer.data)

# @api_view(['GET'])
# def view_kyc_id(request, pk):
#     try:
#         kyc_obj = KYC.objects.get(pk=pk)
#     except KYC.DoesNotExist:
#         return Response({'error': 'KYC record not found'}, status=status.HTTP_404_NOT_FOUND)
#     serializer = KycSerializer(kyc_obj)
#     return Response(serializer.data)






@api_view(['GET', 'POST', 'PATCH'])
@permission_classes([IsAuthenticated])
def kyc_view(request):
    """
    GET: Return current KYC data.
    POST/PATCH: Update KYC data (partial updates allowed for multi-screen submission).
    After a successful update, mark account.kyc_submitted = True and email the account number and PIN.
    """
    user = request.user
    try:
        kyc_record = user.kyc
    except KYC.DoesNotExist:
        if request.method == 'POST':
            kyc_record = KYC.objects.create(user=user)
        else:
            return Response({"error": "KYC record not found."}, status=status.HTTP_404_NOT_FOUND)
    
    if request.method == 'GET':
        serializer = KYCSerializer(kyc_record)
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    serializer = KYCSerializer(kyc_record, data=request.data, partial=True)
    if serializer.is_valid():
        serializer.save()
        
        # Mark account as having submitted KYC
        account = user.account
        account.kyc_submitted = True
        account.save()
        
        # Compose email with account details
        subject = "Your Account Details - KYC Submission Received"
        
        # Inside your kyc_view after successful update:
        html_message = render_to_string('emails/account_details.html', {
            'user': user,
            'account_number': account.account_number,
            'pin_number': account.pin_number,
        })
        send_mail(subject, "", from_email, recipient_list, html_message=html_message)
        from_email = settings.DEFAULT_FROM_EMAIL
        recipient_list = [user.email]
        
        return Response({
            "message": "KYC sumbited successfully. Please check your email for your account details. Payment functionality is paused until your KYC is verified.",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)