import os

import boto3
from botocore.exceptions import ClientError


class KMSClient:
    environment = os.getenv("ENVIRONMENT", "development").lower()

    def __init__(self):
        self.client = boto3.client("secretsmanager")

    def get_secret_value(self, secret_id):
        secret_id = f"{self.environment}-{secret_id}"
        print(secret_id)
        try:
            response = self.client.get_secret_value(SecretId=secret_id)
            return response["SecretString"]
        except ClientError as e:
            if e.response["Error"]["Code"] == "ResourceNotFoundException":
                print(f"The secret with ID '{secret_id}' was not found.")
            elif e.response["Error"]["Code"] == "InvalidRequestException":
                print(f"The request was invalid: {e}")
            elif e.response["Error"]["Code"] == "InvalidParameterException":
                print(f"The request had invalid params: {e}")
            else:
                print(f"Unexpected error: {e}")
        except Exception as e:
            print("Unexpected error:", e)
