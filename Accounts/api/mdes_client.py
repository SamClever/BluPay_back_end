import requests, uuid
from datetime import datetime
from django.conf import settings
import json, base64
import os
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from requests_oauthlib import OAuth1




def mdes_oauth1():
    with open(settings.MDES_RSA_PRIVATE_KEY, "r") as f:
        rsa_key = f.read()
    return OAuth1(
        client_key=settings.MDES_CONSUMER_KEY,
        signature_method="RSA-SHA1",
        rsa_key=rsa_key,
        signature_type="auth_header",
        signature_extras={"body_hash": True}
    )




def load_mastercard_public_key():
    with open(settings.MDES_MC_PUBLIC_KEY, "rb") as f:
        return serialization.load_pem_public_key(f.read())

def encrypt_sensitive_payload(obj: dict):
    # 1. Generate a one-time AES-256 key and IV
    aes_key = os.urandom(32)
    iv      = os.urandom(16)

    # 2. Pad and encrypt the JSON payload with AES-CBC
    plaintext = json.dumps(obj).encode("utf-8")
    pad_len   = 16 - (len(plaintext) % 16)
    padded    = plaintext + bytes([pad_len] * pad_len)
    cipher    = Cipher(algorithms.AES(aes_key), modes.CBC(iv))
    ct        = cipher.encryptor().update(padded) + cipher.encryptor().finalize()

    # 3. Wrap the AES key with Mastercard’s RSA public key (OAEP+SHA256)
    mc_pub = load_mastercard_public_key()
    wrapped_key = mc_pub.encrypt(
        aes_key,
        asym_padding.OAEP(
            mgf=asym_padding.MGF1(hashes.SHA256()),
            algorithm=hashes.SHA256(),
            label=None
        )
    )

    return {
        "encryptedKey": base64.b64encode(wrapped_key).decode(),
        "iv":            iv.hex(),
        "encryptedData": ct.hex(),
        "oaepHashingAlgorithm": "SHA256"
    }





def create_tokenize(funding_pan: str, pan_seq: str, exp_month: int, exp_year: int):
    auth    = mdes_oauth1()
    url     = f"{settings.MDES_BASE_URL}/digitization/static/1/0/tokenize"
    
    # Prepare the encrypted fundingAccountInfo
    funding_info = encrypt_sensitive_payload({
        "accountNumber": funding_pan,
        "panSequenceNumber": pan_seq,
        "expiryMonth": f"{exp_month:02d}",
        "expiryYear":  str(exp_year)
    })

    payload = {
        "tokenRequestorId": settings.MDES_TOKEN_REQUESTOR_ID,
        "tokenType":        "CLOUD",
        "requestId":        str(uuid.uuid4()),
        "taskId":           str(uuid.uuid4()),
        "fundingAccountInfo": funding_info,
        "consumerLanguage":  "en"
    }

    resp = requests.post(url, json=payload, auth=auth, headers={
        "Content-Type": "application/json"
    })
    resp.raise_for_status()
    return resp.json()

