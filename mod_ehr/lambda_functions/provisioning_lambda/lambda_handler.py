import boto3
import json
import os
import base64
from health_connector_base import models

iam = boto3.client("iam")
s3 = boto3.client("s3")
secrets = boto3.client("secretsmanager")

sftp_bucket = os.environ.get("SFTP_BUCKET")
website_bucket = os.environ.get("WEBSITE_BUCKET")

def tenant_provisioning(event, context, **kwargs):

    print("provisioning lambda called")
    print(event, context)
    try:
        # creating s3 sub folder for tenant
        if(event["provider"]=="veradigm"):
            prefix = f'{event["s3_subfolder_name"]}/'
            s3.put_object(
                Bucket=sftp_bucket,
                Key=prefix
            )

        # Create config file in website bucket
        print("Creating config file in website bucket", website_bucket)
        if website_bucket:
            config = {
                "hospitalName": event["name"],
                "appName": "Health Connector",
                "subdomain": event["subdomain"]
            }
            s3.put_object(
                Bucket=website_bucket,
                Key=f"assets/tenants/{event['id']}/configs/config.json",
                Body=json.dumps(config),
                ContentType="application/json"
            )
        
        # Upload logo if present
        if website_bucket and event.get("logo_data"):
            try:
                logo_data = base64.b64decode(event["logo_data"])
                s3.put_object(
                    Bucket=website_bucket,
                    Key=f"assets/tenants/{event['id']}/branding/logo.png",
                    Body=logo_data,
                    ContentType="image/png"
                )
                print(f"Logo uploaded for hospital {event['id']}")
            except Exception as e:
                print(f"Error uploading logo: {e}")
        
        # Update hospital status to ACTIVE
        hospital = models.Hospital.get(event["id"])
        hospital.status = "Active"
        hospital.save()
        print(f"Hospital {event['id']} status updated to ACTIVE")
    except Exception as e:
        print(f"Error during provisioning: {e}")
        raise e

if __name__ == "__main__":
    tenant_provisioning()