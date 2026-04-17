from datetime import datetime, timezone

from health_connector_base.handlers import Response
from health_connector_base.models import Appointment,Patient
from health_connector_base.auth import require_tenant_isolation

def _redact_ride(ride: dict) -> None:
    """Remove pickup/dropoff location details in-place for restricted roles.
    Handles both the current two-leg format and legacy flat-ride records."""
    ride_deletables = ["pickup", "dropoff"]
    if "to_appointment" in ride or "from_appointment" in ride:
        for leg in ("to_appointment", "from_appointment"):
            if leg in ride:
                for deletable in ride_deletables:
                    ride[leg][deletable] = {}
    else:
        for deletable in ride_deletables:
            ride[deletable] = {}


@require_tenant_isolation
def dashboard_handler(event, context):
    group_name = event["requestContext"]["authorizer"]["claims"]["cognito:groups"]
    res = []
    query_params = event.get("queryStringParameters", {})
    if query_params and "hospital_id" in query_params:
        hospital_id = query_params["hospital_id"]

    # valid_patients = {
    #     patient.patient_id for patient in Patient.scan() if patient.via_rider_id and patient.via_rider_id.strip()
    # }
    # time1_1 = datetime.now()
    # print("Time taken to filter valid patients-method-1:", time1_1 - time1)

    restricted_groups = {
        "DallasCountyHealthDepartmentHealthNavigators",
        "HealthcareFacilityStaff",
    }

    if hospital_id == "admin":
        valid_patients = {
            (patient.hospital_id, patient.patient_id) for patient in Patient.scan(
                filter_condition = Patient.via_rider_id.exists() & (Patient.via_rider_id != "")
            )
        }
        for mapping in Appointment.scan(Appointment.end_time >= datetime.now(timezone.utc)):
            if (getattr(mapping, 'hospital_id', None), mapping.patient_id) in valid_patients:
                if group_name in restricted_groups:
                    _redact_ride(mapping.ride)
                res.append(mapping)
    else:
        valid_patients = {
            patient.patient_id for patient in Patient.query(
                hospital_id,
                filter_condition = Patient.via_rider_id.exists() & (Patient.via_rider_id != "")
            )
        }
        for mapping in Appointment.query(hospital_id, filter_condition=(Appointment.end_time >= datetime.now(timezone.utc))):
            if mapping.patient_id in valid_patients:
                if group_name in restricted_groups:
                    _redact_ride(mapping.ride)
                res.append(mapping)

    return Response(res)
