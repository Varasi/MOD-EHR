from health_connector_base import models
from health_connector_base.handlers import APIHandler, Response
from health_connector_base.constants import Status
from health_connector_base.auth import require_tenant_isolation


class LogsHandler(APIHandler):
    model = models.FTPLogs

    @classmethod
    def process_event(cls, event, *args, **kwargs):

        query_params = event.get("queryStringParameters") or {}
        if "hospital_id" not in query_params:
            # Default behavior for other requests
            return super().process_event(event, *args, **kwargs)

        hospital_id = query_params["hospital_id"]
        if hospital_id and hospital_id != "admin":
            logs = list(cls.model.query(hospital_id))
        else:
            logs = list(cls.model.scan())
        records_total = len(logs)

        search = (query_params.get("search") or "").strip().lower()
        if search:
            logs = [log for log in logs if search in log.name.lower()]
        records_filtered = len(logs)

        logs.sort(key=lambda log: log.server_last_modified, reverse=True)

        draw = int(query_params.get("draw", 1))
        start = int(query_params.get("start", 0))
        length = int(query_params.get("length", 0) or records_filtered or 1)
        page = logs[start:start + length]

        return Response(
            body={
                "draw": draw,
                "recordsTotal": records_total,
                "recordsFiltered": records_filtered,
                "data": page,
            },
            status=Status.HTTP_200_OK,
        )

@require_tenant_isolation
def lambda_handler(event, context):
    return LogsHandler.process_event(event)
