import os
import json
import boto3
from health_connector_base import models
from health_connector_base.handlers import APIHandler, Response, PynamoDBEncoder
from health_connector_base.constants import Status


environment = os.environ.get("ENVIRONMENT", "LOCAL")
sftp_s3_bucket = os.environ.get("SFTP_S3_BUCKET")
provisioning_lambda = os.environ.get("PROVISIONING_LAMBDA")


class HospitalAPIHandler(APIHandler):
    model = models.Hospital

    def post(self, event, *args, **kwargs):
        body = json.loads(event["body"])
        logo_data = body.pop("logo_data", None)
        obj = self.model(**body)
        obj.status = "PENDING"
        obj.save()

        payload = json.loads(json.dumps(obj, cls=PynamoDBEncoder))
        if logo_data:
            payload["logo_data"] = logo_data

        lambda_client = boto3.client("lambda")
        print("provisioning_lambda_arn:",provisioning_lambda)
        lambda_client.invoke(
            FunctionName=provisioning_lambda,
            InvocationType="Event",
            Payload=json.dumps(payload),
        )
        return Response(body=obj, status=Status.HTTP_200_OK)


    @classmethod
    def process_event(cls, event: dict, *args, **kwargs):
        response = super(HospitalAPIHandler, cls).process_event(
            event, *args, **kwargs
        )
        return response

def hospitals_handler(event, context):
    return HospitalAPIHandler.process_event(event, context)