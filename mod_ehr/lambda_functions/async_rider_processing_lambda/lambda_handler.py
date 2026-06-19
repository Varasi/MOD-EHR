import json
import re
from health_connector_base.smart_epic import SmartEpicClient, JWTHelper
from health_connector_base.models import Rider, Hospital, RiderHospitalMatch
from health_connector_base.secrets_manager import KMSClient

def _get_jwt(credentials):
    """
    Generates a JWT token.
    """
    return JWTHelper(
        client_id=credentials["epic_client_id"],
        private_key=credentials["epic_private_key"].replace("\\n", "\n"),
        jwks_url=credentials["epic_jwks_url"],
        jwks_kid=credentials["epic_jwks_kid"],
    ).generate_jwt()

def _format_phone_for_epic(phone_no):
    if not phone_no:
        return ""
    digits = re.sub(r'\D', '', phone_no)
    if len(digits) >= 10:
        d = digits[-10:]
        return f"+1 {d[:3]}-{d[3:6]}-{d[6:]}"
    return phone_no

def lambda_handler(event, context):
    print("Async rider processing triggered")
    print(json.dumps(event))
    
    # Extract rider data
    rider_data = event.get("rider", {})
    rider_id = rider_data.get("rider_id")
    
    if not rider_id:
        print("No rider_id found in event payload")
        return {"statusCode": 400, "body": json.dumps({"error": "No rider data provided"})}

    # Map rider_data to the row format expected by get_patient_match
    row = {
        "first_name": rider_data.get("first_name", ""),
        "last_name": rider_data.get("last_name", ""),
        "date_of_birth": rider_data.get("dob", ""),
        "phone": _format_phone_for_epic(rider_data.get("phone_no", ""))
    }
    
    secrets_manager = KMSClient()
    epic_hospitals = Hospital.scan((Hospital.provider == 'epic'))

    for hospital in epic_hospitals:
        hospital_patient_id = None
        try:
            credentials = secrets_manager.get_hospital_secret(hospital.id)
            required_keys = ['epic_client_id', 'epic_private_key', 'epic_jwks_url', 'epic_jwks_kid']
            if not all(k in credentials for k in required_keys):
                print(f"Skipping hospital {hospital.id}: Missing one or more required Epic credentials in Secrets Manager.")
                continue

            jwt_token = _get_jwt(credentials)
            epic_client = SmartEpicClient(jwt_input=jwt_token)

            # Fetch patient data from Epic using the patient_id
            patient_data = epic_client.get_patient_match(row)
            print(f"Patient data for row {row}: {patient_data}")
            if isinstance(patient_data, dict) and "Bundle" in patient_data:
                bundle = patient_data["Bundle"]
                total = int(bundle.get("total", {}).get("@value", "0"))
                
                if total > 0 and "entry" in bundle:
                    entries = bundle["entry"]
                    # xmltodict creates a list for multiple elements, but a dict for a single element
                    if isinstance(entries, dict):
                        entries = [entries]
                    
                    # Extract the Epic Patient FHIR ID from the first match
                    hospital_patient_id = entries[0].get("resource", {}).get("Patient", {}).get("id", {}).get("@value")
                    print(f"Extracted Epic Patient ID: {hospital_patient_id} from hospital {hospital.id}")
        except Exception as e:
            print(f"Failed to process hospital {hospital.id} ({hospital.name}). Error: {str(e)}")
            
        epic_verification_needed = False if hospital_patient_id else True
        
        try:
            match_record = RiderHospitalMatch(
                rider_id=rider_id,
                hospital_id=hospital.id,
                epic_patient_id=hospital_patient_id,
                epic_verification_needed=epic_verification_needed
            )
            match_record.save()
            print(f"Saved match for rider {rider_id} at hospital {hospital.id}. Verification needed: {epic_verification_needed}")
        except Exception as e:
            print(f"Failed to save match record for rider {rider_id} at hospital {hospital.id}: {str(e)}")
            
    try:
        rider = Rider.get(rider_id)
    except Rider.DoesNotExist:
        print(f"Rider {rider_id} not found in database.")
        return {"statusCode": 404, "body": json.dumps({"error": "Rider not found"})}

    return {"statusCode": 200, "body": json.dumps({
        "status": "success", 
        "message": "Processed rider matching for all epic hospitals"
    })}