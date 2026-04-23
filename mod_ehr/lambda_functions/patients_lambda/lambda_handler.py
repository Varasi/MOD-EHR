import os
import json
from pynamodb.exceptions import PutError
from health_connector_base import models
from health_connector_base.handlers import APIHandler, Response, Status, PynamoDBEncoder
from health_connector_base.auth import require_tenant_isolation



class PatientAPIHandler(APIHandler):
    model = models.Patient
 
    def get(self, event, *args, **kwargs):
        # Determine if this is a GET for a single item or a list
        path_params = event.get("pathParameters") or {}
        query_params = event.get("queryStringParameters") or {}
        is_single_item_get = "patient_id" in path_params

        # The @require_tenant_isolation decorator injects these based on the JWT
        user_hospital_id = event.get("user_hospital_id")
        is_admin = event.get("is_admin", False)
        print("is_admin", is_admin)
        print("user_hospital_id", user_hospital_id)

        if is_single_item_get:
            patient_id = path_params["patient_id"]
            # For a single GET, hospital_id is required.
            # Admins can provide it in query string, for others it's from their token.
            hospital_id = user_hospital_id
            if is_admin and "hospital_id" in query_params:
                hospital_id = query_params["hospital_id"]

            if not hospital_id:
                return Response(body={"error": "hospital_id is required"}, status=Status.HTTP_400_BAD_REQUEST)

            try:
                # Use get() with both hash and range keys
                patient = self.model.get(hospital_id, patient_id)
                return Response(body=json.loads(json.dumps(patient, cls=PynamoDBEncoder)), status=Status.HTTP_200_OK)
            except self.model.DoesNotExist:
                return Response(body={"error": "Patient not found"}, status=Status.HTTP_404_NOT_FOUND)
        else:
            # This is a list operation
            print("list operation called")
            hospital_id = user_hospital_id
            if is_admin and "hospital_id" in query_params:
                 hospital_id = query_params.get("hospital_id")

            filter_condition = models.Patient.via_rider_id.exists() & (models.Patient.via_rider_id != "")

            if is_admin and hospital_id == "admin":
                # Admin gets all patients (inefficient scan)
                print("admin getting all patients")
                patients = list(self.model.scan(filter_condition=filter_condition))
            elif hospital_id:
                 # Query for a specific hospital's patients
                print("querying for hospital patients")
                patients = list(self.model.query(hospital_id, filter_condition=filter_condition))
            else:
                return Response(body={"error": "hospital_id is required for non-admin users"}, status=Status.HTTP_400_BAD_REQUEST)

            return Response(body=json.loads(json.dumps(patients, cls=PynamoDBEncoder)), status=Status.HTTP_200_OK)

    def post(self, event, *args, **kwargs):
        body = json.loads(event["body"])
        user_hospital_id = event.get("user_hospital_id")
        is_admin = event.get("is_admin", False)

        # For non-admin users, enforce their own hospital_id
        if not is_admin:
            body["hospital_id"] = user_hospital_id
        # Admin must specify hospital_id in the body
        elif "hospital_id" not in body:
            return Response(body={"error": "hospital_id is required for admin users"}, status=Status.HTTP_400_BAD_REQUEST)
        
        # Check for required fields
        if "patient_id" not in body:
            return Response(body={"error": "patient_id is required"}, status=Status.HTTP_400_BAD_REQUEST)

        patient = self.model(**body)
        try:
            # The default overwrite=False prevents overwriting an existing patient
            patient.save()
            return Response(body=json.loads(json.dumps(patient, cls=PynamoDBEncoder)), status=Status.HTTP_201_CREATED)
        except PutError:
            return Response(body={"error": f"Patient with id {body['patient_id']} already exists for hospital {body['hospital_id']}"}, status=Status.HTTP_409_CONFLICT)
        except Exception as e:
            return Response(body={"error": str(e)}, status=Status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, event, *args, **kwargs):
        path_params = event.get("pathParameters") or {}
        query_params = event.get("queryStringParameters") or {}
        patient_id = path_params["patient_id"]
        user_hospital_id = event.get("user_hospital_id")
        is_admin = event.get("is_admin", False)

        hospital_id = user_hospital_id
        if is_admin and "hospital_id" in query_params:
            hospital_id = query_params["hospital_id"]
        
        if not hospital_id:
            return Response(body={"error": "hospital_id is required"}, status=Status.HTTP_400_BAD_REQUEST)

        try:
            patient = self.model.get(hospital_id, patient_id)
            
            body = json.loads(event["body"])
            
            # Prevent changing primary keys
            if "hospital_id" in body and body["hospital_id"] != hospital_id:
                 return Response(body={"error": "Cannot change hospital_id"}, status=Status.HTTP_400_BAD_REQUEST)
            if "patient_id" in body and body["patient_id"] != patient_id:
                return Response(body={"error": "Cannot change patient_id"}, status=Status.HTTP_400_BAD_REQUEST)

            actions = []
            for key, value in body.items():
                if key not in ('hospital_id', 'patient_id') and hasattr(self.model, key):
                    actions.append(getattr(self.model, key).set(value))
            
            if actions:
                patient.update(actions=actions)

            return Response(body=json.loads(json.dumps(patient, cls=PynamoDBEncoder)), status=Status.HTTP_200_OK)

        except self.model.DoesNotExist:
            return Response(body={"error": "Patient not found"}, status=Status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(body={"error": str(e)}, status=Status.HTTP_500_INTERNAL_SERVER_ERROR)


    def delete(self, event, *args, **kwargs):
        path_params = event.get("pathParameters") or {}
        query_params = event.get("queryStringParameters") or {}
        patient_id = path_params["patient_id"]
        user_hospital_id = event.get("user_hospital_id")
        is_admin = event.get("is_admin", False)

        hospital_id = user_hospital_id
        if is_admin and "hospital_id" in query_params:
            hospital_id = query_params["hospital_id"]

        if not hospital_id:
            return Response(body={"error": "hospital_id is required"}, status=Status.HTTP_400_BAD_REQUEST)

        try:
            patient = self.model.get(hospital_id, patient_id)
            patient.delete()
            return Response(status=Status.HTTP_204_NO_CONTENT)
        except self.model.DoesNotExist:
            return Response(body={"error": "Patient not found"}, status=Status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(body={"error": str(e)}, status=Status.HTTP_500_INTERNAL_SERVER_ERROR)

@require_tenant_isolation
def patients_handler(event, context):
    return PatientAPIHandler.process_event(event, context)
