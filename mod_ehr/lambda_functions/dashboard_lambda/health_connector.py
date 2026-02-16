from datetime import datetime, timezone

from health_connector_base.handlers import Response
from health_connector_base.models import Appointment,Patient


def dashboard_handler(event, context):
    group_name = event["requestContext"]["authorizer"]["claims"]["cognito:groups"]
    ride_deletables = ["pickup", "dropoff"]
    res = []
    query_params = event.get("queryStringParameters", {})
    if query_params and "hospital_id" in query_params:
        hospital_id = query_params["hospital_id"]
    
    # valid_patients = {
    #     patient.patient_id for patient in Patient.scan() if patient.via_rider_id and patient.via_rider_id.strip()
    # }
    # time1_1 = datetime.now()
    # print("Time taken to filter valid patients-method-1:", time1_1 - time1)
    valid_patients = {
            patient.patient_id for patient in Patient.scan(
                filter_condition = Patient.via_rider_id.exists() & (Patient.via_rider_id != "")
            )
        }
    if hospital_id == "admin":
        for mapping in Appointment.scan(Appointment.end_time >= datetime.now(timezone.utc)):
            if mapping.patient_id in valid_patients: 
                if group_name in [
                    "DallasCountyHealthDepartmentHealthNavigators",
                    "HealthcareFacilityStaff",
                ]:
                    for deletable in ride_deletables:
                        mapping.ride[deletable] = {}
                res.append(mapping)
    else:
        for mapping in Appointment.appointments_by_hospitals.query(hospital_id, Appointment.end_time >= datetime.now(timezone.utc)):
            if mapping.patient_id in valid_patients: 
                if group_name in [
                    "DallasCountyHealthDepartmentHealthNavigators",
                    "HealthcareFacilityStaff",
                ]:
                    for deletable in ride_deletables:
                        mapping.ride[deletable] = {}
                res.append(mapping)

    return Response(res)
