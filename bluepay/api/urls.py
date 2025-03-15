from django.urls import path
from .views import (
    transaction_list, transaction_detail,
    creditcard_list, creditcard_detail,
    notification_list, notification_detail
)

urlpatterns = [
   # Transaction endpoints
    path('transactions/', transaction_list, name='transaction_list'),
    path('transactions/<uuid:pk>/', transaction_detail, name='transaction_detail'),
    
    # CreditCard endpoints
    path('creditcards/', creditcard_list, name='creditcard_list'),
    path('creditcards/<uuid:pk>/', creditcard_detail, name='creditcard_detail'),
    
    # Notification endpoints
    path('notifications/', notification_list, name='notification_list'),
    path('notifications/<uuid:pk>/', notification_detail, name='notification_detail'),
]
