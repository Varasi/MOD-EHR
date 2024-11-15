import threading

from geopy.distance import geodesic
from geopy.geocoders import GoogleV3
from health_connector_base import SecretsManager

PROXIMITY_TIME = 15  # min
PROXIMITY_DISTANCE = 1  # km


class LocationManager:
    _connections = threading.local()

    @property
    def geolocator(self):
        connection = getattr(self._connections, "geo_connection", None)
        if not connection:
            self._connections.geo_connection = GoogleV3(
                api_key=SecretsManager().get_secret_value("google_map_api_key"),
                user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                timeout=None,
            )
        return self._connections.geo_connection

    def get_coordinates(self, address: str) -> list:
        if location := self.geolocator.geocode(address):
            return [location.latitude, location.longitude]

    def get_distance(self, coordinates_1, coordinates_2) -> int:
        return geodesic(coordinates_1, coordinates_2).kilometers

    def get_distance_from_address_coords(self, address, coord) -> int:
        if address_coords := self.get_coordinates(address):
            return self.get_distance(address_coords, coord)

    def is_valid_address(self, address: str):
        return self.geolocator.geocode(address)
