from django.urls import path
from .views import (
    transaction_list, transaction_detail,
    notification_list, notification_detail,
    mark_notification_read,
    virtualcard, virtualcard_detail,
    payment_transaction_list, payment_transaction_detail,
    nfcdevice_list, nfcdevice_detail,
    paymenttoken_list, paymenttoken_detail,
    index,
    search_account,
    initiate_transfer,
    confirm_transfer,
    download_receipt,

    initiate_request,
    download_request_receipt,
    settle_request,
    delete_request,
    add_virtual_card,
    add_card,
    top_up,
    withdraw,
    NotificationSettingDetail,
    SecuritySettingDetail,
    ChangePasswordView,
    ChangePinView,

)


urlpatterns = [
    path('', index, name='index'),
   # Transaction endpoints
    path('accounts/search/',               search_account,    name='api-search-account'),
    path('transfer/initiate/',         initiate_transfer, name='api-initiate-transfer'),
    path('transfer/<str:tx_id>/',      transaction_detail,name='api-transaction-detail'),
    path('transfer/<str:tx_id>/confirm/', confirm_transfer,name='api-confirm-transfer'),
    path('transactions/', transaction_list, name='api-transaction-list'),
    path('transactions/<str:tx_id>/', transaction_detail, name='transaction-detail'),
    path(
        'transactions/<str:tx_id>/receipt/download/',
        download_receipt,
        name='download_receipt'
    ),



    # Request endpoints
    path("requests/",         initiate_request,        name="initiate-request"),
    path("requests/<str:tx_id>/receipt/",
        download_request_receipt,
         name="download-request-receipt"),

    path(
        'accounts/<str:account_number>/transactions/<str:transaction_id>/settle/',
        settle_request,
        name='api-transaction-settle'
    ),
    path(
        'accounts/<str:account_number>/transactions/<str:transaction_id>/',
        delete_request,
        name='api-transaction-delete'
    ),
    
    
    # VirtualCard endpoints
    path('virtualcards/', virtualcard, name='virtualcard_list'),
    path('virtualcards/<uuid:pk>/', virtualcard_detail, name='virtualcard_detail'),

    path('add-cards/', add_virtual_card, name='add-virtual-card'),

    path('cards/add/',    add_card,  name='add-card'),
    path('accounts/top-up/', top_up, name='top-up'),
    path('accounts/withdraw/', withdraw, name='withdraw'),
    
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
    path('notifications/read/<str:nid>/', mark_notification_read, name='mark-notification-read'),
    path(
        "notification-settings/",
        NotificationSettingDetail.as_view(),
        name="notification-settings"
    ),


    # Security settings endpoints
    # path("security/", SecuritySettingDetail.as_view(), name="security-settings"),
    # path("security/google-auth/setup/",
    #     SecuritySettingDetail.as_view({"post": "setup_google_auth"}),
    #     name="ga-setup"),
    # path("security/google-auth/verify/",
    #     SecuritySettingDetail.as_view({"post": "verify_google_auth"}),
    #     name="ga-verify"),

    path("security/change-password/",
        ChangePasswordView.as_view(), name="change-password"),
    path("security/change-pin/",
        ChangePinView.as_view(), name="change-pin"),

]
