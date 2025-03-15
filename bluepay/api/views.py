from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from bluepay.models import Transaction, CreditCard, Notification
from .serializers import TransactionSerializer, CreditCardSerializer, NotificationSerializer



# Transaction endpoints
@api_view(['GET'])
def transaction_list(request):
    transactions = Transaction.objects.all()
    serializer = TransactionSerializer(transactions, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def transaction_detail(request, pk):
    try:
        transaction = Transaction.objects.get(pk=pk)
    except Transaction.DoesNotExist:
        return Response({'error': 'Transaction not found'}, status=status.HTTP_404_NOT_FOUND)
    serializer = TransactionSerializer(transaction)
    return Response(serializer.data)



# CreditCard endpoints
@api_view(['GET'])
def creditcard_list(request):
    creditcards = CreditCard.objects.all()
    serializer = CreditCardSerializer(creditcards, many=True)
    return Response(serializer.data)

@api_view(['GET'])
def creditcard_detail(request, pk):
    try:
        creditcard = CreditCard.objects.get(pk=pk)
    except CreditCard.DoesNotExist:
        return Response({'error': 'Credit card not found'}, status=status.HTTP_404_NOT_FOUND)
    serializer = CreditCardSerializer(creditcard)
    return Response(serializer.data)



# Notification endpoints
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
