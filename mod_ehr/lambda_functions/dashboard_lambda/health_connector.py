from datetime import datetime, timezone

from health_connector_base.handlers import Response
from health_connector_base.models import Appointment,Patient


def dashboard_handler(event, context):
    group_name = event["requestContext"]["authorizer"]["claims"]["cognito:groups"]
    ride_deletables = ["pickup", "dropoff"]
    res = []
    
    time1 = datetime.now()
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
    time2 = datetime.now()
    print("Time taken to fetch valid patients-method-2:", time2 - time1)
    for mapping in Appointment.scan(Appointment.end_time >= datetime.now(timezone.utc)):
        if mapping.patient_id in valid_patients: 
            if group_name in [
                "DallasCountyHealthDepartmentHealthNavigators",
                "HealthcareFacilityStaff",
            ]:
                for deletable in ride_deletables:
                    mapping.ride[deletable] = {}
            res.append(mapping)
    time3 = datetime.now()
    print("Time taken to fetch appointments:", time3 - time2)

    return Response(res)
