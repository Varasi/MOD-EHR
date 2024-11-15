from datetime import datetime, timezone
import json
from health_connector_base.handlers import Response
from health_connector_base.models import Dashboard


def dashboard_handler(event, context):
    print('event->'+json.dumps(event))
    group_name = event["requestContext"]["authorizer"]["claims"]["cognito:groups"]
    ride_deletables = ["pickup", "dropoff"]
    res = []
    for mapping in Dashboard.scan(
        Dashboard.end_time >= datetime.now(timezone.utc).timestamp()
    ):
        if group_name in [
            "DallasCountyHealthDepartmentHealthNavigators",
            "HealthcareFacilityStaff",
        ]:
            for deletable in ride_deletables:
                mapping.ride[deletable] = {}
        res.append(mapping)

    return Response(res)
