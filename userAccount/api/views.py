
from userAccount.models import User
from userAccount.api.serializer import UserSerializer,UserRegistrationSerializer
from rest_framework.decorators import api_view
from rest_framework.response import Response
from account.models import KYC
from account.api.serializer import KycSerializer
from account.models import Account
from rest_framework import status
from account.api.serializer import AccountSerializer







@api_view(['POST'])
def register_user(request):
    serializer = UserRegistrationSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response({"message": "User registered successfully."}, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



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