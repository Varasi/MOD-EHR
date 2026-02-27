import json
import boto3
import os
import base64
from boto3.dynamodb.conditions import Attr
 

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table(os.environ["TABLE_NAME"])
 
ROLE_ARN = os.environ["ROLE_ARN"]
BUCKET = os.environ["BUCKET_NAME"]
 
def lambda_handler(event, context):
    username = event.get("username")
    password = event.get("password")
    print("password:",password)
 
    if not username or not password:
        print("[ERROR] No username or password provided")
        return {"isAuthenticated": False}
 
    # secret_id = f"sftp-user/{username}"
 
    try:
        response = table.scan(
            FilterExpression=Attr("sftp_username").eq(username)
        )
        print("response:", response)
 
        items = response.get("Items", [])
        if not items:
            return {"isAuthenticated": False}
        item = items[0]
        print("items:", items)
        print("item:", item)
        if not item:
            return {"isAuthenticated": False}
       
        if item.get("status") != "Active":
            return {"isAuthenticated": False}
 
        stored_password = item.get("sftp_password")
        subfolder = item.get("s3_subfolder_name")
        print("stored_password:", stored_password)
        print("subfolder:", subfolder)
 
        if stored_password == password:
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
 
    except Exception as e:
        print(f"[ERROR] Failed to retrieve or parse secret: {e}")
        return {"isAuthenticated": False}
