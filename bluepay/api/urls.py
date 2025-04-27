from django.urls import path
from .views import (
    transaction_list, transaction_detail,
    notification_list, notification_detail,
    virtualcard, virtualcard_detail,
    payment_transaction_list, payment_transaction_detail,
    nfcdevice_list, nfcdevice_detail,
    paymenttoken_list, paymenttoken_detail,
    index,
    search_account,
    initiate_transfer,
    confirm_transfer,
)

urlpatterns = [
    path('', index, name='index'),
   # Transaction endpoints
    path('accounts/search/',               search_account,    name='api-search-account'),
    path('transfer/initiate/',         initiate_transfer, name='api-initiate-transfer'),
    path('transfer/<str:tx_id>/',      transaction_detail,name='api-transaction-detail'),
    path('transfer/<str:tx_id>/confirm/', confirm_transfer,name='api-confirm-transfer'),

    path('transactions/', transaction_list, name='api-transaction-list'),
    path('transactions/<str:pk>/', transaction_detail, name='api-transaction-detail'),
    
    
    # VirtualCard endpoints
    path('virtualcards/', virtualcard, name='virtualcard_list'),
    path('virtualcards/<uuid:pk>/', virtualcard_detail, name='virtualcard_detail'),
    
    # PaymentTransaction endpoints
    path('transactions/', payment_transaction_list, name='transaction_list'),
    path('transactions/<uuid:pk>/', payment_transaction_detail, name='transaction_detail'),
    
    # NFCDevice endpoints
    path('nfcdevices/', nfcdevice_list, name='nfcdevice_list'),
    path('nfcdevices/<uuid:pk>/', nfcdevice_detail, name='nfcdevice_detail'),
    
    # PaymentToken endpoints
    path('paymenttokens/', paymenttoken_list, name='paymenttoken_list'),
    path('paymenttokens/<uuid:pk>/', paymenttoken_detail, name='paymenttoken_detail'),

    
    # Notification endpoints
    path('notifications/', notification_list, name='notification_list'),
    path('notifications/<uuid:pk>/', notification_detail, name='notification_detail'),
]
