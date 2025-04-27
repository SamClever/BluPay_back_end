from django.db.models.signals import post_save
from django.dispatch import receiver
from Accounts.models import KYC

@receiver(post_save, sender=KYC)
def mark_account_kyc_confirmed(sender, instance, **kwargs):
    """
    When a KYC record is saved and marked face_verified=True,
    flip the user's Account to kyc_confirmed + active.
    """
    acct = instance.user.account
    # Only flip once—we don’t want to overwrite a manual deactivation.
    if instance.face_verified and not acct.kyc_confirmed:
        acct.kyc_submitted = True
        acct.kyc_confirmed = True
        acct.account_status = "active"
        acct.save(update_fields=["kyc_submitted", "kyc_confirmed", "account_status"])
