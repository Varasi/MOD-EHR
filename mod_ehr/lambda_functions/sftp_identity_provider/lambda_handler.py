import json
import boto3
import os
import hmac
from boto3.dynamodb.conditions import Attr


secrets_client = boto3.client("secretsmanager")
dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])
 
ROLE_ARN = os.environ["ROLE_ARN"]
BUCKET = os.environ["BUCKET_NAME"]
ENV = os.environ["ENV"]
 
def lambda_handler(event, context):
    username = event.get("username")
    provided_password = event.get("password")
    print(f"Authenticating user: {username}")
    print(f"Provided password: {provided_password}")
 
    if not username or not provided_password:
        print("[ERROR] No username or password provided")
        return {"isAuthenticated": False}
 
    secret_id = '' # Initialize secret_id
    try:
        # 1. Find hospital info from DynamoDB using the SFTP username
        response = table.scan(
            FilterExpression=Attr("sftp_username").eq(username)
        )

        items = response.get("Items", [])
        if not items:
            print(f"[AUTH] User not found: {username}")
            return {"isAuthenticated": False}
        
        hospital_item = items[0]
        hospital_id = hospital_item.get("id")
        subfolder = hospital_item.get("s3_subfolder_name")

        if not hospital_id or not subfolder:
            print(f"[ERROR] Incomplete hospital data for user: {username}")
            return {"isAuthenticated": False}
            
        if hospital_item.get("status") != "Active":
            print(f"[AUTH] Hospital for user {username} is not active.")
            return {"isAuthenticated": False}

        # 2. Construct the secret name
        secret_id = f"{ENV}-hospital-{hospital_id}"
        print(f"Retrieving secret with ID: {secret_id}")

        # 3. Retrieve the secret from Secrets Manager
        get_secret_value_response = secrets_client.get_secret_value(SecretId=secret_id)
        secret_string = get_secret_value_response["SecretString"]
        secret_dict = json.loads(secret_string)

        stored_password = secret_dict.get("sftp_password")

        if not stored_password:
            print(f"[ERROR] Secret {secret_id} is missing 'sftp_password'.")
            return {"isAuthenticated": False}

        # 4. Compare passwords
        if provided_password == stored_password:
            print(f"[AUTH] Successful authentication for user: {username}")
            # 5. Return success response
            return {
                "isAuthenticated": True,
                "Role": ROLE_ARN,
                "HomeDirectory": f"/{BUCKET}/{subfolder}",
                "Policy": json.dumps(
                    {
                        "Version": "2012-10-17",
                        "Statement": [
                            {
                                "Sid": "VisualEditor0",
                                "Effect": "Allow",
                                "Action": [
                                    "s3:ListBucket",
                                    "s3:GetBucketLocation"
                                ],
                                "Resource": f"arn:aws:s3:::{BUCKET}"
                            },
                            {
                                "Sid": "VisualEditor1",
                                "Effect": "Allow",
                                "Action": [
                                    "s3:PutObject",
                                    "s3:GetObjectAcl",
                                    "s3:GetObject",
                                    "s3:PutObjectRetention",
                                    "s3:DeleteObjectVersion",
                                    "s3:GetObjectAttributes",
                                    "s3:PutObjectLegalHold",
                                    "s3:DeleteObject"
                                ],
                                "Resource": f"arn:aws:s3:::{BUCKET}/{subfolder}/*"
                            }
                        ]
                    }
                )
            }
        else:
            print(f"[AUTH] Invalid password for user: {username}")
            return {"isAuthenticated": False}
 
    except secrets_client.exceptions.ResourceNotFoundException:
        print(f"[ERROR] Secret not found for user: {username} with constructed secret_id: {secret_id}")
        return {"isAuthenticated": False}
    except Exception as e:
        print(f"[ERROR] An unexpected error occurred: {e}")
        return {"isAuthenticated": False}
