import os
import json
import boto3
from pynamodb.exceptions import PutError
from health_connector_base import models
from health_connector_base.handlers import APIHandler, Response, Status
from health_connector_base.models import Patient
from health_connector_base.auth import require_tenant_isolation
import time

environment = os.environ.get("ENVIRONMENT", "LOCAL")
data_populator_lambda_name = os.environ.get("DATA_POPULATOR_LAMBDA_NAME")


class AppointmentAPIHandler(APIHandler):
    model = models.Appointment

    def get(self, event, hash_key=None, *args, **kwargs):
        path_params = event.get("pathParameters") or {}
        query_params = event.get("queryStringParameters") or {}
        is_single_item_get = "id" in path_params

        # if hash_key:
        is_admin = event.get("is_admin", False)
        user_hospital_id = event.get("user_hospital_id")

        if is_single_item_get:
            appointment_id = path_params["id"]
            hospital_id = user_hospital_id
            if is_admin and "hospital_id" in query_params:
                hospital_id = query_params["hospital_id"]

            if not hospital_id:
                return Response(body={"error": "hospital_id is required"}, status=Status.HTTP_400_BAD_REQUEST)

            try:
                appointment = self.model.get(hospital_id, appointment_id)
                return Response(body=appointment, status=Status.HTTP_200_OK)
            except self.model.DoesNotExist:
                return Response(body={"error": "Appointment not found"}, status=Status.HTTP_404_NOT_FOUND)

        hospital_id = user_hospital_id
        if is_admin and "hospital_id" in query_params:
            hospital_id = query_params.get("hospital_id")

        
        filtered_appointments = []
        
        if hospital_id == "admin":
            valid_patients = {
                (patient.hospital_id, patient.patient_id) for patient in Patient.scan(
                    filter_condition = models.Patient.via_rider_id.exists() & (models.Patient.via_rider_id != "")
                )
            }
            print(f"Filtering appointments for admin access. Valid patients: {len(valid_patients)}")
            for hosp_id, pid in valid_patients:
                apts = list(self.model.patient_id_index.query(pid))
                filtered_appointments.extend([a for a in apts if getattr(a, 'hospital_id', None) == hosp_id])

            filtered_appointments.sort(key=lambda apt: apt.start_time, reverse=True)
        else:
            if not hospital_id:
                return Response(body={"error": "hospital_id is required for non-admin users"}, status=Status.HTTP_400_BAD_REQUEST)
                
            valid_patients = {
                patient.patient_id for patient in Patient.query(
                    hospital_id,
                    filter_condition = models.Patient.via_rider_id.exists() & (models.Patient.via_rider_id != "")
                )
            }
            print(f"Filtering appointments for hospital_id: {hospital_id}")
            for pid in valid_patients:
                apts = list(self.model.patient_id_index.query(pid))
                filtered_appointments.extend([a for a in apts if getattr(a, 'hospital_id', None) == hospital_id])
            # filtered_hosp_appointments = list(self.model.appointments_by_hospitals.query(hospital_id))

        return Response(body=filtered_appointments, status=200)
        
    def post(self, event, *args, **kwargs):
        body = json.loads(event["body"])
        user_hospital_id = event.get("user_hospital_id")
        is_admin = event.get("is_admin", False)

        if not is_admin:
            body["hospital_id"] = user_hospital_id
        elif "hospital_id" not in body:
            return Response(body={"error": "hospital_id is required for admin users"}, status=Status.HTTP_400_BAD_REQUEST)

        obj = self.model(**body)
        try:
            obj.save()
            return Response(body=obj, status=Status.HTTP_201_CREATED)
        except PutError:
            return Response(body={"error": "Error saving appointment"}, status=Status.HTTP_409_CONFLICT)
        except Exception as e:
            return Response(body={"error": str(e)}, status=Status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, event, *args, **kwargs):
        path_params = event.get("pathParameters") or {}
        query_params = event.get("queryStringParameters") or {}
        appointment_id = path_params["id"]
        user_hospital_id = event.get("user_hospital_id")
        is_admin = event.get("is_admin", False)

        hospital_id = user_hospital_id
        if is_admin and "hospital_id" in query_params:
            hospital_id = query_params["hospital_id"]

        if not hospital_id:
            return Response(body={"error": "hospital_id is required"}, status=Status.HTTP_400_BAD_REQUEST)

        try:
            appointment = self.model.get(hospital_id, appointment_id)
            
            body = json.loads(event["body"])
            
            if "hospital_id" in body and body["hospital_id"] != hospital_id:
                 return Response(body={"error": "Cannot change hospital_id"}, status=Status.HTTP_400_BAD_REQUEST)
            if "id" in body and body["id"] != appointment_id:
                return Response(body={"error": "Cannot change id"}, status=Status.HTTP_400_BAD_REQUEST)

            actions = []
            for key, value in body.items():
                if key not in ('hospital_id', 'id') and hasattr(self.model, key):
                    actions.append(getattr(self.model, key).set(value))
            
            if actions:
                appointment.update(actions=actions)

            return Response(body=appointment, status=Status.HTTP_200_OK)

        except self.model.DoesNotExist:
            return Response(body={"error": "Appointment not found"}, status=Status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(body={"error": str(e)}, status=Status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, event, *args, **kwargs):
        path_params = event.get("pathParameters") or {}
        query_params = event.get("queryStringParameters") or {}
        appointment_id = path_params["id"]
        user_hospital_id = event.get("user_hospital_id")
        is_admin = event.get("is_admin", False)

        hospital_id = user_hospital_id
        if is_admin and "hospital_id" in query_params:
            hospital_id = query_params["hospital_id"]

        if not hospital_id:
            return Response(body={"error": "hospital_id is required"}, status=Status.HTTP_400_BAD_REQUEST)

        try:
            appointment = self.model.get(hospital_id, appointment_id)
            appointment.delete()
            return Response(status=Status.HTTP_204_NO_CONTENT)
        except self.model.DoesNotExist:
            return Response(body={"error": "Appointment not found"}, status=Status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(body={"error": str(e)}, status=Status.HTTP_500_INTERNAL_SERVER_ERROR)

    @classmethod
    def process_event(cls, event: dict, *args, **kwargs):
        response = super(AppointmentAPIHandler, cls).process_event(
            event, *args, **kwargs
        )
        
        if event["httpMethod"].lower() != "get":
            lambda_client = boto3.client("lambda")
            if data_populator_lambda_name:
                lambda_client.invoke(
                    FunctionName=data_populator_lambda_name,
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

@require_tenant_isolation
def appointments_handler(event, context):
    return AppointmentAPIHandler.process_event(event)
