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
    transaction_history,
    clickpesa_webhook,
    initiate_topup,
    check_payment_methods,
    topup_status,
    topup_history,
    topup_limits,
    # Payout views
    preview_payout,
    initiate_payout,
    payout_status,
    payout_history,
    payout_limits,
    clickpesa_payout_webhook
    
)

urlpatterns = [
    path('', index, name='index'),
   # Transaction endpoints
    path('accounts/search/',               search_account,    name='api-search-account'),
    path('transfer/initiate/',         initiate_transfer, name='api-initiate-transfer'),
    path('transfer/<str:tx_id>/',      transaction_detail,name='api-transaction-detail'),
    path('transfer/<str:tx_id>/confirm/', confirm_transfer,name='api-confirm-transfer'),
    path("transactions/history/", transaction_history, name="transaction-history"),


    #Top up API andpoints
    path('topup/initiate/', initiate_topup, name='initiate_topup'),
    path('topup/methods/', check_payment_methods, name='check_payment_methods'),
    path('topup/status/<str:order_reference>/', topup_status, name='topup_status'),
    path('topup/history/', topup_history, name='topup_history'),
    path('topup/limits/', topup_limits, name='topup_limits'),



    # Payout endpoints
    path('payout/preview/', preview_payout, name='preview_payout'),
    path('payout/initiate/', initiate_payout, name='initiate_payout'),
    path('payout/status/<str:order_reference>/', payout_status, name='payout_status'),
    path('payout/history/', payout_history, name='payout_history'),
    path('payout/limits/', payout_limits, name='payout_limits'),


    # Webhook endpoints
    path('webhooks/clickpesa/', clickpesa_webhook, name='clickpesa_webhook'),
    path('webhooks/clickpesa-payout/', clickpesa_payout_webhook, name='clickpesa_payout_webhook'),



    


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
