import json
import requests
from datetime import datetime
from django.conf import settings

MDES_BASE = settings.MDES_BASE_URL  # e.g. "https://sandbox.api.mastercard.com/mdes"
CERT_PATH = settings.MDES_CERT_PATH  # path to your .p12 or .jks
CERT_PASS = settings.MDES_CERT_PASSWORD

def provision_virtual_card(wallet_number: str, user_id: int):
    """
    Calls MDES Provisioning API to create a new virtual card.
    Returns a dict with pan, exp, cvc, token.
    """
    url = f"{MDES_BASE}/mdes/tokenize/v1/accounts/{wallet_number}"
    # Build your payload per MDES spec
    payload = {
        "clientDetails": {
            "clientUserId": str(user_id),
            "clientTransactionId": f"txn-{user_id}-{int(datetime.utcnow().timestamp())}"
        },
        "account": {
            "cardAcceptorId": settings.MDES_CARD_ACCEPTOR_ID,
            "bin": settings.MDES_BIN,              # your BIN
        },
        # add any additional required sections here
    }

    # MDES often requires your payload to be signed with the client cert.
    response = requests.post(
        url,
        data=json.dumps(payload),
        cert=(CERT_PATH, CERT_PASS),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Basic {settings.MDES_BASIC_AUTH}",  # if required
            # other MDES-specific headers, e.g. x-apikey, x-request-id…
        },
        timeout=30
    )
    response.raise_for_status()
    data = response.json()
    # Parse out the fields (adapt to MDES response structure)
    pan = data["account"]["pan"]
    exp = data["account"]["expirationDate"]      # e.g. "MMYY"
    cvc = data["securityCode"]
    token = data.get("tokenReference")           # if tokenized
    return {"pan": pan, "exp": exp, "cvc": cvc, "token": token}