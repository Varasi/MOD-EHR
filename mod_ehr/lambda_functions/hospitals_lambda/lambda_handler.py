import os
import json
import boto3
from health_connector_base import models
from health_connector_base.handlers import APIHandler

environment = os.environ.get("ENVIRONMENT", "LOCAL")

class HospitalAPIHandler(APIHandler):
    model = models.Hospital

    @classmethod
    def process_event(cls, event: dict, *args, **kwargs):
        response = super(HospitalAPIHandler, cls).process_event(
            event, *args, **kwargs
        )
        return response

def hospitals_handler(event, context):
    return HospitalAPIHandler.process_event(event, context)