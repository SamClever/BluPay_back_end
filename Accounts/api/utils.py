import boto3
from botocore.exceptions import ClientError, BotoCoreError
import os
import phonenumbers
import pycountry
from phonenumbers import COUNTRY_CODE_TO_REGION_CODE
from django.conf import settings

rekog = boto3.client(
    "rekognition",
    aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    region_name=settings.AWS_REGION,
)


def compare_faces_aws(id_path: str, selfie_path: str, threshold: float = 80.0):
    """
    Compares two local image files using AWS Rekognition.
    Returns: (match: bool, similarity: float)
    """
    try:
        # Read and validate image data
        with open(id_path, "rb") as f:
            id_bytes = f.read()
        with open(selfie_path, "rb") as f:
            selfie_bytes = f.read()

        if not id_bytes or not selfie_bytes:
            raise ValueError("One or both image files are empty.")

        # Make Rekognition API call
        response = rekog.compare_faces(
            SourceImage={"Bytes": id_bytes},
            TargetImage={"Bytes": selfie_bytes},
            SimilarityThreshold=threshold,
        )

        matches = response.get("FaceMatches", [])
        if not matches:
            return False, 0.0

        similarity = matches[0].get("Similarity", 0.0)
        return True, round(similarity, 2)

    except (ClientError, BotoCoreError) as aws_error:
        print(f"[AWS Error] {aws_error}")
        return False, 0.0

    except Exception as e:
        print(f"[Error] {e}")
        return False, 0.0


def get_country_phone_code_choices():
    """
    Returns a list of tuples [(dial_code, label), …] sorted by country name,
    where dial_code is e.g. "+1" and label is "United States (+1)".
    """
    seen = set()
    choices = []
    for dial, regions in COUNTRY_CODE_TO_REGION_CODE.items():
        for region in regions:
            if (region, dial) in seen:
                continue
            seen.add((region, dial))
            country = pycountry.countries.get(alpha_2=region)
            name = country.name if country else region
            choices.append((f"+{dial}", f"{name} (+{dial})"))
    return sorted(choices, key=lambda x: x[1])
