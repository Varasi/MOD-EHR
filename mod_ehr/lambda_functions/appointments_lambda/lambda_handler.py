import os
import json
import boto3
from health_connector_base import models
from health_connector_base.handlers import APIHandler
from health_connector_base.models import Patient
from health_connector_base.handlers import Response
import time

environment = os.environ.get("ENVIRONMENT", "LOCAL")


class AppointmentAPIHandler(APIHandler):
    model = models.Appointment

    def get(self, event, hash_key=None, *args, **kwargs):
        query_params = event.get("queryStringParameters", {})
        if query_params and "hospital_id" in query_params:
            hospital_id = query_params["hospital_id"]

        if hash_key:
            # Single record retrieval
            return super().get(event, hash_key, *args, **kwargs)

        
        filtered_appointments = []
        
        if hospital_id == "admin":
            valid_patients = {
                patient.patient_id for patient in Patient.scan(
                    filter_condition = models.Patient.via_rider_id.exists() & (models.Patient.via_rider_id != "")
                )
            }
            print(f"Filtering appointments for admin access. Valid patients: {valid_patients}")
            for pid in valid_patients:
                filtered_appointments.extend(list(self.model.patient_id_index.query(pid)))

            filtered_appointments.sort(key=lambda apt: apt.start_time, reverse=True)
        else:
            valid_patients = {
                patient.patient_id for patient in Patient.scan(
                    filter_condition = models.Patient.via_rider_id.exists() & (models.Patient.via_rider_id != "") & (models.Patient.hospital_id == hospital_id)
                )
            }
            print(f"Filtering appointments for hospital_id: {hospital_id}")
            for pid in valid_patients:
                filtered_appointments.extend(list(self.model.patient_id_index.query(pid)))
            # filtered_hosp_appointments = list(self.model.appointments_by_hospitals.query(hospital_id))
            # for apt in filtered_hosp_appointments:
            #     if apt.patient_id in valid_patients:
            #         filtered_appointments.append(apt)
            filtered_appointments.sort(key=lambda apt: apt.start_time, reverse=True)

        return Response(body=filtered_appointments, status=200)
        

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
        # if isinstance(response, dict) and "body" in response:
        #     try:
        #         # Parse the body JSON
        #         response_body = json.loads(response["body"])

        #         # Filter required fields
        #         if isinstance(response_body, list):  # Ensure it's a list of appointments
        #             filtered_data = [
        #                 {
        #                     "id": item["id"],
        #                     "location": item["location"],
        #                     "patient_name": item["patient_name"],
        #                     "start_time": item["start_time"],
        #                     "end_time": item["end_time"],
        #                     "status": item["status"]
        #                 }
        #                 for item in response_body
        #                 if all(k in item for k in ["id", "location", "patient_name", "start_time", "end_time", "status"])
        #             ]

        #             # Update response body
        #             response["body"] = json.dumps(filtered_data)

        #     except json.JSONDecodeError as e:
        #         print(f"Error decoding JSON: {e}")
        return response


def appointments_handler(event, context):
    return AppointmentAPIHandler.process_event(event)
