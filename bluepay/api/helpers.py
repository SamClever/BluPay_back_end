from bluepay.models import Notification

def send_notification(user, notification_type, message="", amount=0):
    settings = getattr(user, "notification_settings", None)
    if not settings or not settings.general:
        return

    # Optional: check specific type setting
    type_check = {
        "payment_success": settings.payments,
        "payment_failed": settings.payments,
        "login": settings.login_alerts,
        "promo_offer": settings.promotions,
        "app_update": settings.app_updates,
    }
    if notification_type in type_check and not type_check[notification_type]:
        return

    Notification.objects.create(
        user=user,
        notification_type=notification_type,
        message=message,
        amount=amount
    )
