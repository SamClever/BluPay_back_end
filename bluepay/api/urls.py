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
    topup_view, 
    clickpesa_webhook,
    mobile_money_payout_view,
    query_payout_status
    
)

urlpatterns = [
    path('', index, name='index'),
   # Transaction endpoints
    path('accounts/search/',               search_account,    name='api-search-account'),
    path('transfer/initiate/',         initiate_transfer, name='api-initiate-transfer'),
    path('transfer/<str:tx_id>/',      transaction_detail,name='api-transaction-detail'),
    path('transfer/<str:tx_id>/confirm/', confirm_transfer,name='api-confirm-transfer'),


    #Top up API andpoints
    path("topup/", topup_view, name="topup_view"),
    path("webhook/clickpesa/", clickpesa_webhook, name="clickpesa_webhook"),
    path("payout/", mobile_money_payout_view, name="payout" ),
    path("payout/status/<str:order_reference>/", query_payout_status, name="payout_status"),


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
