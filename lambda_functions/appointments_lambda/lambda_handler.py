import contextlib
import os

import boto3
from health_connector_base import models
from health_connector_base.handlers import APIHandler

environment = os.environ.get("ENVIRONMENT", "LOCAL")


class AppointmentAPIHandler(APIHandler):
    model = models.Appointment

    @classmethod
    def process_event(cls, event: dict, *args, **kwargs):
        response = super(AppointmentAPIHandler, cls).process_event(
            event, *args, **kwargs
        )
        # if event["httpMethod"].lower() != "get":
        #     lambda_client = boto3.client("lambda")
        #     lambda_client.invoke(
        #         FunctionName=f"HealthConnector{environment.title()}DataPopulator",
        #         InvocationType="Event",
        #         Payload=b"{}",
        #     )
        return response

    def delete(self, event: dict, hash_key, *args, **kwargs):
        response = super(AppointmentAPIHandler, self).delete(
            event, hash_key, *args, **kwargs
        )
        with contextlib.suppress(models.Dashboard.DoesNotExist):
            models.Dashboard.get(hash_key).delete()
            print(f"deleted {hash_key} object from Dashboard")
        return response


def appointments_handler(event, context):
    print("apppointments handler called")
    return AppointmentAPIHandler.process_event(event)
