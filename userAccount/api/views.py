
from userAccount.models import User
from userAccount.api.serializer import UserSerializer
from rest_framework.decorators import api_view
from rest_framework.response import Response
from account.models import KYC
from account.api.serializer import KycSerializer
from account.models import Account
from account.api.serializer import AccountSerializer

@api_view()
def view_allUsers(request):
    user = User.objects.all()
    serializer = UserSerializer(user,many=True)
    return Response(serializer.data)
@api_view()
def user_id(request,pk):
    user = User.objects.get(pk=pk)
    serializer = UserSerializer(user)
    return Response(serializer.data)