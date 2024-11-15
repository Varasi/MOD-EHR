import json
import traceback
from datetime import datetime
from typing import Any

from health_connector_base.constants import ORIGINS_ALLOWED, Status
from health_connector_base.exceptions import HandlerBaseException, NotFound
from pynamodb.constants import DATETIME_FORMAT
from pynamodb.models import Model


class PynamoDBEncoder(json.JSONEncoder):
    def default(self, obj: Model | Any):
        if hasattr(obj, "attribute_values"):
            return obj.attribute_values
        elif isinstance(obj, datetime):
            return obj.strftime(DATETIME_FORMAT)
        return super(PynamoDBEncoder, self).default(obj)


class Response(dict):
    headers = {
        "content-type": "application/json",
        "Access-Control-Allow-Origin": ORIGINS_ALLOWED,
    }

    def __init__(
        self,
        body: Any = None,
        status: int = Status.HTTP_200_OK,
        is_base64_encoded=False,
        headers=None,
    ):
        self["isBase64Encoded"] = is_base64_encoded
        self["headers"] = self.headers | (headers or {})
        self["statusCode"] = status
        self["body"] = json.dumps(body, cls=PynamoDBEncoder) if body else b"[]"


class APIHandler:
    model: Model = None

    def __init__(self, event):
        """
        Args:
            event: The event data to initialize the instance.
        Raises:
            ValueError: If the model is not configured.
        """
        if self.model is None:
            raise ValueError("Model not Configured")
        self.event = event

    def check_permissions(self, event: dict, response: Response):
        return True

    def post_request(self, event: dict, response: Response) -> Response:
        return response

    def get_object(self, hash_key: Any):
        """
        Retrieves an object from the model using the provided hash key.
        Args:
            hash_key: The key to retrieve the object from the model.
        Returns:
            The object corresponding to the hash key.
        Raises:
            NotFound: If the object with the given hash key is not found in the model.
        """
        try:
            return self.model.get(hash_key)
        except self.model.DoesNotExist as e:
            raise NotFound from e

    def retrieve(self, event: dict, hash_key: Any, *args, **kwargs):
        """
        Retrieves an object using the provided hash key and returns it as a response.
        Args:
            event: The event data.
            hash_key: The key to retrieve the object.
        Returns:
            Response: The response containing the retrieved object.
        Raises:
            NotFound: If the object with the given hash key is not found.
        """

        obj = self.get_object(hash_key)
        return Response(body=obj, status=Status.HTTP_200_OK)

    def get(self, event: dict, hash_key=None, *args, **kwargs):
        """
        Retrieves an object based on the hash key or lists all objects if no key is provided.
        Args:
            event: The event data.
            hash_key: The key to retrieve the object (optional).
        Returns:
            Response: The response containing the retrieved object or list of objects.
        """
        if hash_key:
            return self.retrieve(event, hash_key, *args, **kwargs)
        return Response(body=list(self.model.scan()), status=Status.HTTP_200_OK)

    def post(self, event: dict, *args, **kwargs):
        """
        Creates and saves an object from the event data using the provided hash key.
        Args:
            event: The event data containing the object details.
        Returns:
            Response: The response containing the saved object.
        """
        obj = self.model(**json.loads(event["body"]))
        obj.save()
        return Response(body=obj, status=Status.HTTP_200_OK)

    def put(self, event: dict, hash_key: Any, *args, **kwargs):
        """
        Updates an object with the data from the event using the provided hash key.
        Args:
            event: The event data containing the updated object details.
            hash_key: The key to update the object.
        Returns:
            Response: The response containing the updated object.
        """
        obj = self.get_object(hash_key)
        for key, value in json.loads(event["body"]).items():
            setattr(obj, key, value)
        obj.save()
        return Response(body=obj, status=Status.HTTP_200_OK)

    def delete(self, event: dict, hash_key: Any, *args, **kwargs):
        """
        Updates an object with the data from the event using the provided hash key.
        Args:
            event: The event data containing the updated object details.
            hash_key: The key to update the object.
        Returns:
            Response: The response containing the updated object.
        """
        obj = self.get_object(hash_key)
        obj.delete()
        return Response(status=Status.HTTP_204_NO_CONTENT)

    @classmethod
    def process_event(cls, event: dict, *args, **kwargs):
        """
        Processes the event based on the HTTP method and delegates to the corresponding handler.

        Args:
            event: The event data.

        Returns:
            The result of handling the event based on the HTTP method.
        """
        cls = cls(event)
        http_method = event["httpMethod"].lower()
        handler = getattr(cls, http_method, cls.http_method_not_allowed)
        hash_key = (event.get("pathParameters") or {}).get(cls.model._hash_keyname)
        try:
            return handler(event, hash_key)
        except HandlerBaseException as e:
            return cls.handle_exception(e)

    def http_method_not_allowed(self, event):
        """
        Returns a response indicating that the HTTP method is not allowed.
        Args:
            event: The event data triggering the method not allowed response.
        Returns:
            Response: The response indicating HTTP method not allowed.
        """
        return Response(status=Status.HTTP_405_METHOD_NOT_ALLOWED)

    def handle_exception(self, exc):
        """
        Handles exceptions by returning an appropriate response based on the type of exception.
        Args:
            exc: The exception to handle.
        Returns:
            Response: The response based on the exception type.
        """
        if isinstance(exc, HandlerBaseException):
            return Response(status=exc.status, body={"detail": exc.detail})
        print(traceback.format_exc())
        # for uncaught exceptions
        raise exc
