from health_connector_base.constants import Status


class HandlerBaseException(Exception):
    status = Status.HTTP_500_INTERNAL_SERVER_ERROR
    detail = "A server error occurred."

    def __init__(self, detail=None, *args) -> None:
        if detail:
            self.detail = detail


class NotFound(HandlerBaseException):
    status = Status.HTTP_404_NOT_FOUND
    detail = "Not Found."


class ValidationError(HandlerBaseException):
    status = Status.HTTP_400_BAD_REQUEST
    detail = "Invalid input."
