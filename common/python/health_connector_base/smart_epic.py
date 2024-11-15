import time
import uuid

import jwt
import requests
import xmltodict
from health_connector_base import CacheManager, SecretsManager


class JWTHelper(object):
    def __init__(self):
        secrets_manager = SecretsManager()
        self.client_id = secrets_manager.get_secret_value("epic_client_id")
        self.jwt_private_key = secrets_manager.get_secret_value("epic_private_key")
        self.jwt_public_key = secrets_manager.get_secret_value("epic_public_key")
        self.token_url = "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token"
        self.auth_headers = {"Content-Type": "application/x-www-form-urlencoded"}
        self.token_expiry_offset = 180  # in seconds
        self.token_buffer = 10  # in seconds

    @property
    def get_auth_body(self) -> dict:
        return {
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": self.client_id,
        }

    @property
    def jwt_payload(self) -> dict:
        return {
            "iss": self.client_id,
            "sub": self.client_id,
            "aud": self.token_url,
            "jti": str(uuid.uuid4()),
            "exp": int(time.time()) + self.token_expiry_offset,
            "nbf": int(time.time()) + self.token_buffer,
            "iat": time.time(),
        }

    @property
    def jwt_headers(self) -> dict:
        return {"alg": "RS256", "typ": "JWT", "x5c": [self.jwt_public_key]}

    def generate_jwt(self) -> str:
        return jwt.encode(
            payload=self.jwt_payload,
            key=self.jwt_private_key,
            algorithm="RS256",
            headers=self.jwt_headers,
        )


class SmartEpicClient:
    def __init__(self, jwt_input: str):
        self.cache_manager = CacheManager()
        self.token_url = "https://fhir.epic.com/interconnect-fhir-oauth/oauth2/token"
        self.base_url = "https://fhir.epic.com/interconnect-fhir-oauth/api/FHIR/R4"
        self.jwt = jwt_input
        self.token = None

    def set_access_token(self) -> None:
        r = requests.post(
            self.token_url,
            data=self.request_body(),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if r.ok:
            self.token = r.json()["access_token"]

    def add_auth_header(self, headers: dict) -> dict:
        headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def request_body(self) -> dict:
        return {
            "grant_type": "client_credentials",
            "client_assertion_type": "urn:ietf:params:oauth:client-assertion-type:jwt-bearer",
            "client_assertion": self.jwt,
        }

    def get_appointments(self, patient_id: str) -> str:
        if not self.token:
            self.set_access_token()
        if self.token and patient_id:
            r = requests.get(
                f"{self.base_url}/Appointment",
                headers=self.add_auth_header({}),
                params={
                    "service-category": "appointment",
                    "status": "accepted",
                    "patient": patient_id,
                },
            )
            if r.ok:
                return xmltodict.parse(r.text)
        return ""

    def get_location_data(self, location_id: str) -> str:
        if not self.token:
            self.set_access_token()
        if self.token and location_id:
            if value := self.cache_manager.get_value(location_id):
                return value
            r = requests.get(
                f"{self.base_url}/Location/{location_id}",
                headers=self.add_auth_header({}),
            )
            if r.ok:
                address = ",".join(
                    _["@value"]
                    for _ in xmltodict.parse(r.text)["Location"]["address"].values()
                )
                self.cache_manager.set_value(location_id, address)
                return address
        return ""
