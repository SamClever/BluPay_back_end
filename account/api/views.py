
from userAccount.models import User
from userAccount.api.serializer import UserSerializer
from account.api.serializer import AccountSerializer
from account.api.serializer import KycSerializer
from account.models import Account,KYC
from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view()
def view_account(request):
    account = Account.objects.all()
    serializer = AccountSerializer(account,many=True)
    return Response(serializer.data)
@api_view()
def view_account_id(request,pk):
    account = Account.objects.get(pk=pk)
    serializer = AccountSerializer(account)
    return Response(serializer.data)