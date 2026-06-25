from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from health_connector_base.handlers import Response
from health_connector_base.models import Appointment, Patient, RiderHospitalMatch
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

    # Empty for now. Add any future groups here that should NOT see pickup/dropoff details
    restricted_groups = {
    }

    tz = ZoneInfo("America/Chicago")
    now = datetime.now(tz)
    start_of_today = now.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_today = start_of_today + timedelta(days=1)

    start_of_today_utc = start_of_today.astimezone(timezone.utc)
    end_of_today_utc = end_of_today.astimezone(timezone.utc)

    if hospital_id == "admin":
        valid_patients = {
            (match.hospital_id, match.epic_patient_id) for match in RiderHospitalMatch.scan(
                filter_condition = RiderHospitalMatch.epic_patient_id.exists() & (RiderHospitalMatch.epic_verification_needed == False)
            )
        }
        for mapping in Appointment.scan((Appointment.end_time >= start_of_today_utc) & (Appointment.end_time < end_of_today_utc)):
            if (getattr(mapping, 'hospital_id', None), mapping.patient_id) in valid_patients:
                if group_name in restricted_groups:
                    _redact_ride(mapping.ride)
                res.append(mapping)
    else:
        valid_patients = {
            match.epic_patient_id for match in RiderHospitalMatch.scan(
                filter_condition = (RiderHospitalMatch.hospital_id == hospital_id) &
                                   RiderHospitalMatch.epic_patient_id.exists() & 
                                   (RiderHospitalMatch.epic_verification_needed == False)
            )
        }
        for mapping in Appointment.query(hospital_id, filter_condition=((Appointment.end_time >= start_of_today_utc) & (Appointment.end_time < end_of_today_utc))):
            if mapping.patient_id in valid_patients:
                if group_name in restricted_groups:
                    _redact_ride(mapping.ride)
                res.append(mapping)

    return Response(res)
