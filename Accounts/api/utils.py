import boto3
import os
import phonenumbers
import pycountry
from phonenumbers import COUNTRY_CODE_TO_REGION_CODE

# Assumes your AWS creds are in env vars or ~/.aws/credentials
rekog = boto3.client('rekognition', region_name='us-east-1')

def compare_faces_aws(id_path: str, selfie_path: str, threshold: float = 80.0):
    """
    Compares two local files via AWS Rekognition.
    Returns (match: bool, similarity: float).
    """
    with open(id_path,     'rb') as f: id_bytes     = f.read()
    with open(selfie_path, 'rb') as f: selfie_bytes = f.read()

    resp = rekog.compare_faces(
        SourceImage={'Bytes': id_bytes},
        TargetImage={'Bytes': selfie_bytes},
        SimilarityThreshold=threshold
    )
    matches = resp.get('FaceMatches', [])
    if not matches:
        return False, 0.0

    sim = matches[0]['Similarity']
    return True, round(sim, 2)


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
            choices.append((f'+{dial}', f'{name} (+{dial})'))
    return sorted(choices, key=lambda x: x[1])