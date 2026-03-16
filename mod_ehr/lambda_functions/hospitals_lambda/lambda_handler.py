import os
import json
import boto3
from botocore.exceptions import ClientError
from health_connector_base import models
from health_connector_base.handlers import APIHandler, Response, PynamoDBEncoder
from health_connector_base.constants import Status


environment = os.environ.get("ENVIRONMENT", "LOCAL")
sftp_s3_bucket = os.environ.get("SFTP_S3_BUCKET")
provisioning_lambda = os.environ.get("PROVISIONING_LAMBDA")
secrets_client = boto3.client("secretsmanager")


class HospitalAPIHandler(APIHandler):
    model = models.Hospital

    def _get_secret_name(self, hospital_id):
        return f"{environment.lower()}-hospital-{hospital_id}"

    def _update_secret(self, hospital_id, secret_data):
        if not secret_data:
            return
        secret_name = self._get_secret_name(hospital_id)
        try:
            secrets_client.create_secret(
                Name=secret_name,
                SecretString=json.dumps(secret_data)
            )
        except ClientError as e:
            if e.response['Error']['Code'] == 'ResourceExistsException':
                secrets_client.put_secret_value(
                    SecretId=secret_name,
                    SecretString=json.dumps(secret_data)
                )
            else:
                print(f"Error updating secret: {e}")

    def _get_secret(self, hospital_id):
        secret_name = self._get_secret_name(hospital_id)
        try:
            response = secrets_client.get_secret_value(SecretId=secret_name)
            if 'SecretString' in response:
                return json.loads(response['SecretString'])
        except ClientError:
            return {}
        return {}

    def _delete_secret(self, hospital_id):
        secret_name = self._get_secret_name(hospital_id)
        try:
            secrets_client.delete_secret(SecretId=secret_name, ForceDeleteWithoutRecovery=True)
        except ClientError as e:
            print(f"Error deleting secret: {e}")

    def get(self, event, *args, **kwargs):
        if event.get("pathParameters") and event["pathParameters"].get("id"):
            pk = event["pathParameters"]["id"]
            try:
                obj = self.model.get(pk)
                data = json.loads(json.dumps(obj, cls=PynamoDBEncoder))
                # Enrich with secrets for detail view
                secrets = self._get_secret(pk)
                data.update(secrets)
                return Response(body=data, status=Status.HTTP_200_OK)
            except self.model.DoesNotExist:
                 return Response(body={"error": "Not Found"}, status=Status.HTTP_404_NOT_FOUND)
        
        # For list operations, get all hospitals and enrich them with secrets.
        response = super(HospitalAPIHandler, self).get(event, *args, **kwargs)
        hospitals = json.loads(response['body'])
        
        for hospital in hospitals:
            secrets = self._get_secret(hospital['id'])
            if secrets:
                hospital.update(secrets)
            
        return Response(body=hospitals, status=Status.HTTP_200_OK)

    def post(self, event, *args, **kwargs):
        body = json.loads(event["body"])
        logo_data = body.pop("logo_data", None)

        # Extract secrets
        secret_keys = ['epic_client_id', 'epic_private_key', 'epic_jwks_url', 'epic_jwks_kid', 's3_subfolder_name', 'sftp_username', 'sftp_password']
        secret_data = {k: body[k] for k in secret_keys if k in body}
        
        # Remove highly sensitive fields from DB body
        keys_to_remove_from_db = ['epic_client_id', 'epic_private_key', 'epic_jwks_url', 'epic_jwks_kid', 'sftp_password']
        for k in keys_to_remove_from_db:
            if k in body:
                del body[k]

        obj = self.model(**body)
        obj.status = "PENDING"
        obj.save()

        if secret_data:
            self._update_secret(obj.id, secret_data)

        payload = json.loads(json.dumps(obj, cls=PynamoDBEncoder))
        if logo_data:
            payload["logo_data"] = logo_data
        
        if secret_data:
            payload.update(secret_data)

        lambda_client = boto3.client("lambda")
        print("provisioning_lambda_arn:",provisioning_lambda)
        lambda_client.invoke(
            FunctionName=provisioning_lambda,
            InvocationType="Event",
            Payload=json.dumps(payload),
        )
        return Response(body=obj, status=Status.HTTP_200_OK)

    def put(self, event, *args, **kwargs):
        body = json.loads(event["body"])
        logo_data = body.pop("logo_data", None)
        pk = event["pathParameters"]["id"]
        obj = self.model.get(pk)
        
        secret_keys = ['epic_client_id', 'epic_private_key', 'epic_jwks_url', 'epic_jwks_kid', 's3_subfolder_name', 'sftp_username', 'sftp_password']
        secret_data = {k: body[k] for k in secret_keys if k in body}
        
        if secret_data:
            current_secrets = self._get_secret(pk)
            current_secrets.update(secret_data)
            self._update_secret(pk, current_secrets)
            
        keys_to_remove_from_db = ['epic_client_id', 'epic_private_key', 'epic_jwks_url', 'epic_jwks_kid', 'sftp_password']
        for k in keys_to_remove_from_db:
            if k in body:
                del body[k]

        for k, v in body.items():
            setattr(obj, k, v)
        obj.save()

        payload = json.loads(json.dumps(obj, cls=PynamoDBEncoder))
        if logo_data:
            payload["logo_data"] = logo_data
        
        all_secrets = self._get_secret(pk)
        payload.update(all_secrets)

        lambda_client = boto3.client("lambda")
        lambda_client.invoke(
            FunctionName=provisioning_lambda,
            InvocationType="Event",
            Payload=json.dumps(payload),
        )
        return Response(body=obj, status=Status.HTTP_200_OK)

    def delete(self, event, *args, **kwargs):
        pk = event["pathParameters"]["id"]
        obj = self.model.get(pk)

        # Prepare payload for provisioning_lambda to delete assets
        payload = json.loads(json.dumps(obj, cls=PynamoDBEncoder))
        payload["action"] = "DELETE"

        self._delete_secret(pk)

        # Invoke provisioning_lambda to delete S3 assets
        lambda_client = boto3.client("lambda")
        lambda_client.invoke(
            FunctionName=provisioning_lambda,
            InvocationType="Event",  # Fire-and-forget
            Payload=json.dumps(payload),
        )

        # Delete the hospital record from DynamoDB
        obj.delete()

        # Return a 204 No Content response, which is standard for successful DELETE
        return Response(status=Status.HTTP_204_NO_CONTENT)


    @classmethod
    def process_event(cls, event: dict, *args, **kwargs):
        response = super(HospitalAPIHandler, cls).process_event(
            event, *args, **kwargs
        )
        return response

def hospitals_handler(event, context):
    return HospitalAPIHandler.process_event(event, context)