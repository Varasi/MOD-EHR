from health_connector_base import models
from health_connector_base.handlers import APIHandler, Response
from health_connector_base.constants import Status


class LogsHandler(APIHandler):
    model = models.FTPLogs

    @classmethod
    def process_event(cls, event, *args, **kwargs):

        query_params = event.get("queryStringParameters", {})
        if query_params and "hospital_id" in query_params:
            hospital_id = query_params["hospital_id"]
            logs = []
            # Query using the GSI
            if hospital_id and hospital_id != "admin":
                logs = list(cls.model.logs_by_hospital.query(hospital_id))
                print(f"Queried logs for hospital_id {hospital_id}: {logs}")
            else:
                logs = list(cls.model.scan())
            return Response(body=logs, status=Status.HTTP_200_OK)
        
        # Default behavior for other requests
        return super().process_event(event, *args, **kwargs)

def lambda_handler(event, context):
    return LogsHandler.process_event(event)
