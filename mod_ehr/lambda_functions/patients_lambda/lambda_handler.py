import os
import json
from health_connector_base import models
from health_connector_base.handlers import APIHandler, Response, Status

class PatientAPIHandler(APIHandler):
    model = models.Patient

    def get(self, event, hash_key=None, *args, **kwargs):
        if hash_key:
            # Single record retrieval
            return super().get(event, hash_key, *args, **kwargs)
        
        query_params = event.get("queryStringParameters", {})
        if query_params and "hospital_id" in query_params:
            hospital_id = query_params["hospital_id"]
            print("hospital_id:", hospital_id)
        
        
        
        # hospital_id = event["requestContext"]["authorizer"]["claims"]["custom:hospital_id"]
        
        # patient_id = event.get("pathParameters", {}).get("patient_id")
        # if patient_id:
        #     try:
        #         patient = self.model.get(patient_id)
        #         # Admin can get any patient, other users can only get from their hospital
        #         if hospital_id == "admin" or patient.hospital_id == hospital_id:
        #             return Response(body=patient, status=Status.HTTP_200_OK)
        #         else:
        #             return Response(body={"message": "Forbidden"}, status=Status.HTTP_403_FORBIDDEN)
        #     except self.model.DoesNotExist:
        #         return Response(body={"message": "Not Found"}, status=Status.HTTP_404_NOT_FOUND)

            if hospital_id == "admin":
                # Admin gets all patients
                patients = list(self.model.scan(filter_condition = models.Patient.via_rider_id.exists() & (models.Patient.via_rider_id != "")))
            else:
                # Other users get patients for their hospital using the GSI
                patients = list(self.model.scan(filter_condition = models.Patient.via_rider_id.exists() & (models.Patient.via_rider_id != "") & (models.Patient.hospital_id == hospital_id)))
        
            return Response(body=patients, status=Status.HTTP_200_OK)

    # def post(self, event, *args, **kwargs):
    #     body = json.loads(event["body"])
    #     hospital_id = event["requestContext"]["authorizer"]["claims"]["custom:hospital_id"]

    #     if hospital_id == "admin":
    #         # Admin must specify hospital_id in the body
    #         if "hospital_id" not in body:
    #             return Response(body={"message": "hospital_id is required for admin"}, status=Status.HTTP_400_BAD_REQUEST)
    #     else:
    #         # For non-admin users, enforce their own hospital_id
    #         body["hospital_id"] = hospital_id
        
    #     obj = self.model(**body)
    #     obj.save()
    #     return Response(body=obj, status=Status.HTTP_200_OK)

    # def put(self, event, *args, **kwargs):
    #     patient_id = event["pathParameters"]["patient_id"]
    #     hospital_id = event["requestContext"]["authorizer"]["claims"]["custom:hospital_id"]
        
    #     try:
    #         patient = self.model.get(patient_id)
    #         if hospital_id != "admin" and patient.hospital_id != hospital_id:
    #             return Response(body={"message": "Forbidden"}, status=Status.HTTP_403_FORBIDDEN)
            
    #         body = json.loads(event["body"])
            
    #         # Admins can change hospital_id, others cannot.
    #         if hospital_id != "admin" and "hospital_id" in body and body["hospital_id"] != hospital_id:
    #              return Response(body={"message": "Cannot change hospital_id"}, status=Status.HTTP_403_FORBIDDEN)

    #         actions = []
    #         for key, value in body.items():
    #             if key != "patient_id": # Don't allow changing the hash key
    #                 actions.append(getattr(self.model, key).set(value))
            
    #         patient.update(actions=actions)
    #         return Response(body=patient, status=Status.HTTP_200_OK)

    #     except self.model.DoesNotExist:
    #         return Response(body={"message": "Not Found"}, status=Status.HTTP_404_NOT_FOUND)

    # def delete(self, event, *args, **kwargs):
    #     patient_id = event["pathParameters"]["patient_id"]
    #     hospital_id = event["requestContext"]["authorizer"]["claims"]["custom:hospital_id"]

    #     try:
    #         patient = self.model.get(patient_id)
    #         if hospital_id != "admin" and patient.hospital_id != hospital_id:
    #             return Response(body={"message": "Forbidden"}, status=Status.HTTP_403_FORBIDDEN)
            
    #         patient.delete()
    #         return Response(status=Status.HTTP_204_NO_CONTENT)
    #     except self.model.DoesNotExist:
    #         return Response(body={"message": "Not Found"}, status=Status.HTTP_404_NOT_FOUND)


def patients_handler(event, context):
    return PatientAPIHandler.process_event(event, context)
