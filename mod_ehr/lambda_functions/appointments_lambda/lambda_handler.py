import os
import json
import boto3
from datetime import datetime, timedelta, timezone
from health_connector_base import models
from health_connector_base.handlers import APIHandler
from health_connector_base.models import Patient
from health_connector_base.handlers import Response
import inspect
import time

environment = os.environ.get("ENVIRONMENT", "LOCAL")


class AppointmentAPIHandler(APIHandler):
    time_0 = time.time()
    model = models.Appointment
    time_00 = time.time()
    print("Time taken to connect to Dynamodb:", time_00 - time_0)


    @staticmethod
    def to_dict(pynamo_obj):
        result = {}
        for name, attr in pynamo_obj.get_attributes().items():
            result[name] = getattr(pynamo_obj, name)
        return result
    
    def get(self, event, hash_key=None, *args, **kwargs):
        # print("LOADED FROM:", inspect.getfile(self.model))
        # print("AppointmentAPIHandler GET called")
        #get time-1
        time_1 = time.time()
        if hash_key:
            # Single record retrieval
            return super().get(event, hash_key, *args, **kwargs)
        # get time-2
        time_2 = time.time()
        print("Time taken for super get function:", time_2 - time_1)

        # Pagination parameters from DataTables
        query_params = event.get('queryStringParameters', {}) or {}
        page = int(query_params.get('page', 1))
        limit = int(query_params.get('limit', 25))
        search = query_params.get('search', '').lower()
        offset = (page - 1) * limit

        valid_patients = {
            patient.patient_id for patient in Patient.scan(
                filter_condition = models.Patient.via_rider_id.exists() & (models.Patient.via_rider_id != "")
            )
        }
        # get time-3
        time_3 = time.time()
        print("Time taken to fetch valid patients", time_3 - time_2)

        filtered_appointments = []
        for pid in valid_patients:
            filtered_appointments.extend(list(self.model.patient_id_index.query(pid)))

        filtered_appointments.sort(key=lambda apt: apt.start_time, reverse=True)
        # get time-4
        time_4 = time.time()
        print("Time taken to fetch appointments for valid patients:", time_4 - time_3)

        
        storing_appoitments = [
            self.to_dict(apt) for apt in filtered_appointments 
        ]
        # get time-5
        time_5 = time.time()
        print("Time taken to convert appointments to dict:", time_5 - time_4)
        if search:
            search = search.lower()
            search_filtered_appointments = [
                apt for apt in storing_appoitments
                if search in apt.get("id", "").lower() or
                search in apt.get("patient_name", "").lower() or
                search in apt.get("location", "").lower() or
                search in apt.get("status", "").lower()
            ]
            filtered_appointments = search_filtered_appointments
        # get time-6
        time_6 = time.time()
        print("Time taken for search filtering:", time_6 - time_5)

        total_records = len(filtered_appointments)
        paginated_data = filtered_appointments[offset:offset + limit]
        # print("Total records after filtering:", total_records)
        
        # Format response for DataTables
        response_data = {
            'draw': int(query_params.get('draw', 1)),
            'recordsTotal': total_records,
            'recordsFiltered': total_records,
            'data': [apt for apt in paginated_data]
        }
        # get time-7
        time_7 = time.time()
        print("Time taken for pagination and response formatting:", time_7 - time_6)
        return Response(body=response_data, status=200)



    @classmethod
    def process_event(cls, event: dict, *args, **kwargs):
        time1 = time.time()
        response = super(AppointmentAPIHandler, cls).process_event(
            event, *args, **kwargs
        )
        time2 = time.time()
        print("Time taken by super().process_event:", time2 - time1)
        
        if event["httpMethod"].lower() != "get":
            lambda_client = boto3.client("lambda")
            lambda_client.invoke(
                FunctionName=f"HealthConnector{environment.title()}DataPopulator",
                InvocationType="Event",
                Payload=b"{}",
            )
        # time3 = datetime.now()
        # if isinstance(response, dict) and "body" in response:
        #     try:
        #         # Parse the body JSON
        #         response_body = json.loads(response["body"])

                
                # if isinstance(response_body, list):  # Ensure it's a list of appointments
                #     # Calculate 8 months ago from now
                #     # six_months_ago = datetime.now(timezone.utc) - timedelta(days=60)
                    
                #     filtered_data = []
                #     # time5 = datetime.now()
                #     valid_patients = {
                #         patient.patient_id for patient in Patient.scan() if patient.via_rider_id and patient.via_rider_id.strip()
                #     }
                #     # time6 = datetime.now()
                #     # print("Time taken to fetch valid patients-method-old:", time6 - time5)
                #     for item in response_body:
                #         # Check if item has all required fields
                #         if all(k in item for k in ["id", "location", "patient_name", "start_time", "end_time", "status"]): #patient_id add in the list
                #             # Check if appointment is within last 8 months
                #             if item["patient_id"] in valid_patients:
                #                 try:
                #                     # appointment_date = datetime.fromisoformat(item["start_time"].replace('Z', '+00:00'))
                #                     # if appointment_date >= six_months_ago:
                #                     filtered_data.append({
                #                         "id": item["id"],
                #                         "location": item["location"],
                #                         "patient_name": item["patient_name"],
                #                         "start_time": item["start_time"],
                #                         "end_time": item["end_time"],
                #                         "status": item["status"]
                #                     })
                #                 except (ValueError, TypeError):
                #                     # Skip records with invalid date format
                #                     continue

                #     # Update response body
                #     response["body"] = json.dumps(filtered_data)

            # except json.JSONDecodeError as e:
            #     print(f"Error decoding JSON: {e}")
        # time4 = datetime.now()
        # print("Time taken to filter and modify response body:", time4 - time3)
        return response


def appointments_handler(event, context):
    return AppointmentAPIHandler.process_event(event)
