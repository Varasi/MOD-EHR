import contextlib

import requests
from health_connector_base import SecretsManager


class Via(object):
    def __init__(self):
        secrets_manager = SecretsManager()
        self.client_id = secrets_manager.get_secret_value("via_client_id")
        self.client_secret = secrets_manager.get_secret_value("via_client_secret")
        self.via_api_key = secrets_manager.get_secret_value("via_api_key")
        self.via_auth_url = (
            "https://trip-api.auth.us-east-1.amazoncognito.com/oauth2/token"
        )
        self.via_api_url = "us-east-1.trip-api.ridewithvia.com"
        self.token = None
        self.TRIP_STATUSES = ["CONFIRMED", "FINISHED"]

    def set_token(self):
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {"grant_type": "client_credentials"}
        response = requests.post(
            self.via_auth_url,
            headers=headers,
            data=data,
            auth=(self.client_id, self.client_secret),
        )
        if response.ok:
            self.token = response.json().get("access_token")

    @property
    def auth_header(self):
        return {"x-api-key": self.via_api_key, "Authorization": self.token}

    # TODO Map Ride Vehicle Details from Data
    def get_ride_details(self, rides):
        if not self.token:
            self.set_token()
        for ride in rides:
            body = {"trip_id": ride["trip_id"]}
            r = requests.get(
                f"https://{self.via_api_url}/trips/details/",
                params=body,
                headers=self.auth_header,
            )
            if r.ok:
                with contextlib.suppress(KeyError):
                    resp = r.json()
                    ride.update({"driver_info": resp["trip_details"]["driver_info"]})
                    ride.update({"vehicle_info": resp["trip_details"]["vehicle_info"]})
        return rides

    def get_trips(self, rider_id) -> dict:
        if not self.token:
            self.set_token()

        data = {"page_list_size": 100, "rider_id": rider_id}
        trips = []
        for status in self.TRIP_STATUSES:
            data["trip_status"] = status
            r = requests.get(
                f"https://{self.via_api_url}/trips/get",
                params=data,
                headers=self.auth_header,
            )
            if r.ok:
                resp = r.json().get("trips", [])
                trips += self.get_ride_details(resp)
        print(trips)
        return {"trips": trips}
