import os
import json
import boto3
from pynamodb.exceptions import PutError
from health_connector_base import models
from health_connector_base.handlers import APIHandler, Response, Status, PynamoDBEncoder
from health_connector_base.auth import require_tenant_isolation

lambda_client = boto3.client('lambda')

def trigger_async_rider_processing(rider_data, action="create"):
    # Make sure your main Lambda role has 'lambda:InvokeFunction' permissions
    try:
        lambda_name = os.environ.get('ASYNC_RIDER_LAMBDA_NAME')
        if not lambda_name:
            raise ValueError("ASYNC_RIDER_LAMBDA_NAME environment variable is not set")
            
        lambda_client.invoke(
            FunctionName=lambda_name,
            InvocationType='Event',  # 'Event' makes the invocation asynchronous
            Payload=json.dumps({"rider": rider_data, "action": action})
        )
    except Exception as e:
        print(f"Failed to trigger async processing: {str(e)}")


class RiderAPIHandler(APIHandler):
    model = models.Rider
 
    def get(self, event, *args, **kwargs):
        path_params = event.get("pathParameters") or {}
        query_params = event.get("queryStringParameters") or {}
        is_single_item_get = "rider_id" in path_params

        # Injected by @require_tenant_isolation
        user_hospital_id = event.get("user_hospital_id")
        is_admin = event.get("is_admin", False)
        print("is_admin", is_admin)
        print("user_hospital_id", user_hospital_id)

        if not is_admin:
            if not user_hospital_id:
                return Response(body={"error": "Access denied. hospital_id required."}, status=Status.HTTP_403_FORBIDDEN)
            
            if is_single_item_get:
                rider_id = path_params["rider_id"]
                try:
                    match = models.RiderHospitalMatch.get(rider_id, user_hospital_id)
                    if match.epic_verification_needed:
                        return Response(body={"error": "Access denied. Rider match not verified."}, status=Status.HTTP_403_FORBIDDEN)
                    
                    rider = self.model.get(rider_id)
                    rider_dict = {
                        "patient_id": match.epic_patient_id,
                        "name": f"{rider.first_name} {rider.last_name}",
                        "via_rider_id": rider.rider_id,
                        "phone": rider.phone_no,
                        "dob": rider.dob,
                        "hospital_id": user_hospital_id
                    }
                    return Response(body=rider_dict, status=Status.HTTP_200_OK)
                except (models.RiderHospitalMatch.DoesNotExist, self.model.DoesNotExist):
                    return Response(body={"error": "Rider not found or not matched to your hospital"}, status=Status.HTTP_404_NOT_FOUND)
            else:
                matches = list(models.RiderHospitalMatch.scan(
                    filter_condition = (models.RiderHospitalMatch.hospital_id == user_hospital_id) &
                                       models.RiderHospitalMatch.epic_patient_id.exists() & 
                                       (models.RiderHospitalMatch.epic_verification_needed == False)
                ))
                
                riders_data = []
                for m in matches:
                    try:
                        rider = self.model.get(m.rider_id)
                        riders_data.append({
                            "patient_id": m.epic_patient_id,
                            "name": f"{rider.first_name} {rider.last_name}",
                            "via_rider_id": rider.rider_id,
                            "phone": rider.phone_no,
                            "dob": rider.dob,
                            "hospital_id": user_hospital_id
                        })
                    except self.model.DoesNotExist:
                        continue
                return Response(body=riders_data, status=Status.HTTP_200_OK)

        hospitals = {h.id: h.name for h in models.Hospital.scan()}

        if is_single_item_get:
            rider_id = path_params["rider_id"]
            try:
                rider = self.model.get(rider_id)
                rider_dict = json.loads(json.dumps(rider, cls=PynamoDBEncoder))
                
                matches = list(models.RiderHospitalMatch.query(rider_id))
                rider_dict["matches"] = [{
                    "hospital_id": m.hospital_id,
                    "hospital_name": hospitals.get(m.hospital_id, "Unknown Hospital"),
                    "epic_verification_needed": m.epic_verification_needed,
                    "epic_patient_id": m.epic_patient_id
                } for m in matches]
                
                return Response(body=rider_dict, status=Status.HTTP_200_OK)
            except self.model.DoesNotExist:
                return Response(body={"error": "Rider not found"}, status=Status.HTTP_404_NOT_FOUND)
        else:
            print("list operation called")
            print("admin getting all riders")
            riders = list(self.model.scan())
            riders_data = json.loads(json.dumps(riders, cls=PynamoDBEncoder))

            matches = list(models.RiderHospitalMatch.scan())
            matches_by_rider = {}
            for m in matches:
                if m.rider_id not in matches_by_rider:
                    matches_by_rider[m.rider_id] = []
                matches_by_rider[m.rider_id].append({
                    "hospital_id": m.hospital_id,
                    "hospital_name": hospitals.get(m.hospital_id, "Unknown Hospital"),
                    "epic_verification_needed": m.epic_verification_needed,
                    "epic_patient_id": m.epic_patient_id
                })
            
            for r in riders_data:
                r["matches"] = matches_by_rider.get(r["rider_id"], [])

            return Response(body=riders_data, status=Status.HTTP_200_OK)

    def post(self, event, *args, **kwargs):
        body = json.loads(event["body"])
        is_admin = event.get("is_admin", False)

        if not is_admin:
            return Response(body={"error": "Access denied. Only admins can access riders."}, status=Status.HTTP_403_FORBIDDEN)
        
        required_fields = ["rider_id", "first_name", "last_name", "phone_no", "dob"]
        for field in required_fields:
            val = body.get(field)
            if val is None or (isinstance(val, str) and val.strip() == ""):
                return Response(body={"error": f"{field} is required and cannot be null or empty"}, status=Status.HTTP_400_BAD_REQUEST)

        rider = self.model(**body)
        try:
            rider.save()
            
            rider_dict = json.loads(json.dumps(rider, cls=PynamoDBEncoder))
            trigger_async_rider_processing(rider_dict, action="create")
            
            return Response(body=rider_dict, status=Status.HTTP_201_CREATED)
        except PutError:
            return Response(body={"error": f"Rider with id {body['rider_id']} already exists"}, status=Status.HTTP_409_CONFLICT)
        except Exception as e:
            return Response(body={"error": str(e)}, status=Status.HTTP_500_INTERNAL_SERVER_ERROR)

    def put(self, event, *args, **kwargs):
        path_params = event.get("pathParameters") or {}
        rider_id = path_params["rider_id"]
        is_admin = event.get("is_admin", False)

        if not is_admin:
            return Response(body={"error": "Access denied. Only admins can access riders."}, status=Status.HTTP_403_FORBIDDEN)

        try:
            rider = self.model.get(rider_id)
            
            body = json.loads(event["body"])
            
            new_rider_id = body.get("rider_id")
            changing_rider_id = new_rider_id and new_rider_id != rider_id
            
            if changing_rider_id:
                try:
                    self.model.get(new_rider_id)
                    return Response(body={"error": f"Rider with id {new_rider_id} already exists"}, status=Status.HTTP_409_CONFLICT)
                except self.model.DoesNotExist:
                    pass

            actions = []
            trigger_async = changing_rider_id
            
            for key, value in body.items():
                if key not in ('rider_id',) and hasattr(self.model, key):
                    if value is None or (isinstance(value, str) and value.strip() == ""):
                        return Response(body={"error": f"{key} cannot be null or empty"}, status=Status.HTTP_400_BAD_REQUEST)
                    
                    if getattr(rider, key, None) != value:
                        actions.append(getattr(self.model, key).set(value))
                        
                        if key != 'status':
                            trigger_async = True
            
            if changing_rider_id:
                # DynamoDB partition keys cannot be updated directly.
                # We need to create a new item with the updated data and delete the old one.
                new_rider_kwargs = {}
                for attr_name in rider.get_attributes().keys():
                    val = getattr(rider, attr_name)
                    if val is not None:
                        new_rider_kwargs[attr_name] = val
                
                for key, value in body.items():
                    if hasattr(self.model, key):
                        new_rider_kwargs[key] = value
                
                new_rider = self.model(**new_rider_kwargs)
                new_rider.save()
                rider.delete()
                rider = new_rider
            else:
                if actions:
                    rider.update(actions=actions)

            rider_dict = json.loads(json.dumps(rider, cls=PynamoDBEncoder))
            if trigger_async:
                trigger_async_rider_processing(rider_dict, action="update")
                
            return Response(body=rider_dict, status=Status.HTTP_200_OK)

        except self.model.DoesNotExist:
            return Response(body={"error": "Rider not found"}, status=Status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(body={"error": str(e)}, status=Status.HTTP_500_INTERNAL_SERVER_ERROR)

    def delete(self, event, *args, **kwargs):
        path_params = event.get("pathParameters") or {}
        rider_id = path_params["rider_id"]
        is_admin = event.get("is_admin", False)

        if not is_admin:
            return Response(body={"error": "Access denied. Only admins can access riders."}, status=Status.HTTP_403_FORBIDDEN)

        try:
            rider = self.model.get(rider_id)

            # Find and delete all associated hospital match records
            matches_to_delete = models.RiderHospitalMatch.query(rider_id)
            with models.RiderHospitalMatch.batch_write() as batch:
                for match in matches_to_delete:
                    batch.delete(match)

            rider.delete()
            return Response(status=Status.HTTP_204_NO_CONTENT)
        except self.model.DoesNotExist:
            return Response(body={"error": "Rider not found"}, status=Status.HTTP_404_NOT_FOUND)
        except Exception as e:
            return Response(body={"error": str(e)}, status=Status.HTTP_500_INTERNAL_SERVER_ERROR)

@require_tenant_isolation
def riders_handler(event, context):
    return RiderAPIHandler.process_event(event, context)