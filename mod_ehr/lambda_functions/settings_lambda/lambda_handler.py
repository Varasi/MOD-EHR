from health_connector_base import models  # noqa
from health_connector_base.handlers import APIHandler, Response # noqa
import json
from health_connector_base.constants import ORIGINS_ALLOWED, Status
from health_connector_base.auth import require_tenant_isolation

class SettingsHandler(APIHandler):
    model = models.Settings

    @classmethod
    def process_event(cls, event, *args, **kwargs):

        query_params = event.get("queryStringParameters", {})
        if query_params and "hospital_id" in query_params:
            hospital_id = query_params["hospital_id"]
            settings = []
            # Query using the GSI
            if hospital_id:
                settings = list(cls.model.settings_by_hospital.query(hospital_id))
                print(f"Queried settings for hospital_id {hospital_id}: {settings}")
            print(f"Response body: {settings}")
            return Response(body=settings, status=Status.HTTP_200_OK)
        
        # Default behavior for other requests
        return super().process_event(event, *args, **kwargs)

@require_tenant_isolation
def settings_handler(event, context):
    return SettingsHandler.process_event(event)
