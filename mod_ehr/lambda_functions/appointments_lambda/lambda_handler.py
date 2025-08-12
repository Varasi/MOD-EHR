import os
import json
import boto3
from datetime import datetime, timedelta, timezone
from health_connector_base import models
from health_connector_base.handlers import APIHandler
from health_connector_base.models import Patient

environment = os.environ.get("ENVIRONMENT", "LOCAL")


class AppointmentAPIHandler(APIHandler):
    model = models.Appointment

    @classmethod
    def process_event(cls, event: dict, *args, **kwargs):
        response = super(AppointmentAPIHandler, cls).process_event(
            event, *args, **kwargs
        )
        
        if event["httpMethod"].lower() != "get":
            lambda_client = boto3.client("lambda")
            lambda_client.invoke(
                FunctionName=f"HealthConnector{environment.title()}DataPopulator",
                InvocationType="Event",
                Payload=b"{}",
            )
        if isinstance(response, dict) and "body" in response:
            try:
                # Parse the body JSON
                response_body = json.loads(response["body"])

                
                if isinstance(response_body, list):  # Ensure it's a list of appointments
                    # Calculate 8 months ago from now
                    # six_months_ago = datetime.now(timezone.utc) - timedelta(days=60)
                    
                    filtered_data = []
                    valid_patients = {
                        patient.patient_id for patient in Patient.scan() if patient.via_rider_id and patient.via_rider_id.strip()
                    }
                    for item in response_body:
                        # Check if item has all required fields
                        if all(k in item for k in ["id", "location", "patient_name", "start_time", "end_time", "status"]): #patient_id add in the list
                            # Check if appointment is within last 8 months
                            if item["patient_id"] in valid_patients:
                                try:
                                    # appointment_date = datetime.fromisoformat(item["start_time"].replace('Z', '+00:00'))
                                    # if appointment_date >= six_months_ago:
                                    filtered_data.append({
                                        "id": item["id"],
                                        "location": item["location"],
                                        "patient_name": item["patient_name"],
                                        "start_time": item["start_time"],
                                        "end_time": item["end_time"],
                                        "status": item["status"]
                                    })
                                except (ValueError, TypeError):
                                    # Skip records with invalid date format
                                    continue

                    # Update response body
                    response["body"] = json.dumps(filtered_data)

            except json.JSONDecodeError as e:
                print(f"Error decoding JSON: {e}")
        return response


def appointments_handler(event, context):
    return AppointmentAPIHandler.process_event(event)
