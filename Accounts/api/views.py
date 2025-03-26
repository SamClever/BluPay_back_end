
from userAccount.models import User
from userAccount.api.serializer import UserSerializer
from Accounts.api.serializer import AccountSerializer, KycSerializer
from Accounts.models import Account, KYC
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status



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
@api_view(['GET'])
def view_kyc(request):
    kyc_records = KYC.objects.all()
    serializer = KycSerializer(kyc_records, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def view_kyc_id(request, pk):
    try:
        kyc_obj = KYC.objects.get(pk=pk)
    except KYC.DoesNotExist:
        return Response({'error': 'KYC record not found'}, status=status.HTTP_404_NOT_FOUND)
    serializer = KycSerializer(kyc_obj)
    return Response(serializer.data)