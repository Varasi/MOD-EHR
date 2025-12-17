import contextlib
import csv
import threading
from datetime import datetime, timedelta, timezone
from functools import cached_property
import pytz
import boto3
from health_connector_base.constants import (
    DIFF_MATCH_IN_SEC,
    LOCATION_DIFF,
    MOCK_DATA,
    VIA_RIDE_MOCK,
)
from health_connector_base.location_manager import LocationManager
from health_connector_base.models import Appointment, FTPLogs, Patient, Settings
from health_connector_base.smart_epic import JWTHelper, SmartEpicClient
from health_connector_base.via import Via
from pydantic_models import AppointmentsList
central_tz = pytz.timezone("America/Chicago")
utc_tz = pytz.utc
class AppointmentsMapperWithVia:
    """
    Returns the patient-rider mapping as a dictionary.
    Returns:
        dict: The patient-rider mapping.
    """

    settings = ["subsequent_period", "prior_period"]

    def __init__(self) -> None:
        self._connections = threading.local()

    @cached_property
    def prior_period(self):
        with contextlib.suppress(Settings.DoesNotExist):
            return int(Settings.get("prior_period").value) * 60
        return DIFF_MATCH_IN_SEC

    @cached_property
    def subsequent_period(self):
        with contextlib.suppress(Settings.DoesNotExist):
            return int(Settings.get("subsequent_period").value) * -60
        return -900

    def get_patient_mapping(self) -> dict:
        """
        Returns the patient-rider mapping as a dictionary.
        Returns:
            dict: The patient-rider mapping.
        """

        return {
            "epic": {
                patient.patient_id: patient.via_rider_id
                for patient in Patient.scan(
                    filter_condition=(
                        (Patient.via_rider_id) and (Patient.provider == "epic")
                    )
                )
            },
            "veradigm": {
                patient.patient_id: patient.via_rider_id
                for patient in Patient.scan(
                    filter_condition=(
                        (Patient.via_rider_id) and (Patient.provider == "veradigm")
                    )
                )
            },
            "all": {
                patient.patient_id: patient.via_rider_id
                for patient in Patient.scan(
                    filter_condition=(None and (Patient.via_rider_id))
                )
            },
        }

    def _get_jwt(self):
        """
        Generates a JWT token.
        Returns:
            The generated JWT token.
        """

        return JWTHelper().generate_jwt()

    def _map_participant_details(self, participant: dict):
        """
        Maps the details of a participant.
        Args:
            participant_type (list): The type of participant.
            participant (dict): The participant details.
        Returns:
            dict: The mapped participant details.
        """
        return participant["actor"]["display"]["@value"]

    def get_matching_ride(
        self, address: str, trips: list, appointment_start_time: int
    ) -> dict:
        """
        Returns the matching ride based on the address, trips, and appointment start time.
        Args:
            address (str): The address.
            trips (list): The list of trips.
            appointment_start_time (int): The appointment start timestamp..
        Returns:
            The matching ride.
        """
        match_ride = {}
        prev_diff = 1e9
        prev_location_diff = 1e9
        for trip in trips:
            cur_diff = int(appointment_start_time - trip["dropoff_eta"])
            cur_location_diff = int(
                LocationManager().get_distance_from_address_coords(
                    address,
                    [
                        trip.get("dropoff", {}).get("lat", 0),
                        trip.get("dropoff", {}).get("lng", 0),
                    ],
                )
            )
            print(f"subsequent_period: {self.subsequent_period}, cur_diff: {cur_diff}, prior_period: {self.prior_period}")
            print(f"cur_diff: {cur_diff}, prev_diff: {prev_diff}, cur_location_diff: {cur_location_diff}, prev_location_diff: {prev_location_diff}")
            if (
                self.subsequent_period <= cur_diff <= self.prior_period
                and cur_diff < prev_diff
                and cur_location_diff <= LOCATION_DIFF
                and cur_location_diff <= prev_location_diff
            ):
                prev_diff = cur_diff
                match_ride = trip
                prev_location_diff = cur_location_diff
        print("Matched ride:", match_ride)
        return match_ride

    def _map_participants_data(
        self, appointment: dict, smart_client: SmartEpicClient
    ) -> dict:
        """
        Maps participant data from an appointment to a dictionary.

        Args:
            appointment (dict): The appointment data.
            smart_client (SmartEpicClient): The SmartEpicClient instance.
            start_time (int): The start time of the appointment.

        Returns:
            dict: A dictionary containing mapped participant data.
        """
        result = {}
        for participant in appointment["participant"]:
            participant_type = participant["actor"]["reference"]["@value"].split("/")
            if participant_type[0] == "Patient":
                result["patient_name"] = participant["actor"]["display"]["@value"]
                result["patient_id"] = participant_type[-1]
            elif participant_type[0] == "Location":
                if location_response := smart_client.get_location_data(
                    participant_type[-1]
                ):
                    result["location"] = location_response
        return result

    def epic_with_via(self, patient_mapping: dict):
        smart_client = SmartEpicClient(self._get_jwt())
        appointment_objs = []
        for patient_key, rider_id in patient_mapping["epic"].items():
            # trips = Via().get_trips(rider_id).get("trips")
            if appointments := smart_client.get_appointments(patient_key):
                for appointment in appointments["Bundle"]["entry"]:
                    try:
                        appointment = appointment["resource"]["Appointment"]
                        status = appointment["status"]["@value"]
                        start_time = datetime.strptime(
                            appointment["start"]["@value"], "%Y-%m-%dT%H:%M:%SZ"
                        )
                        end_time = datetime.strptime(
                            appointment["end"]["@value"], "%Y-%m-%dT%H:%M:%SZ"
                        )
                        result = {
                            "id": appointment["id"]["@value"],
                            "status": status,
                            "start_time": start_time,
                            "end_time": end_time,
                            "provider": "epic",
                        } | self._map_participants_data(appointment, smart_client)
                        # result |= {
                        #     "ride": self.get_matching_ride(
                        #         result["location"], trips, int(start_time.timestamp())
                        #     )
                        #     or VIA_RIDE_MOCK
                        # }
                        appointment_objs.append(Appointment(**result))
                    except KeyError as e:
                        print(e.args)
        with Appointment.batch_write() as batch:
            for appointment in appointment_objs:
                batch.save(appointment)

    @property
    def s3_connection(self):
        connection = getattr(self._connections, "connection", None)
        if connection is None:
            self._connections.connection = boto3.Session().client("s3")
        return self._connections.connection

    def get_file_data(self, bucket_name: str, file_key: str):
        response = self.s3_connection.get_object(Bucket=bucket_name, Key=file_key)
        return (
            response["Body"].read().decode("utf-8").splitlines(),
            response["LastModified"],
        )

    def veradigm_with_via(self, patient_mapping: dict, file_key: str, bucket_name: str):
        data, last_modified = self.get_file_data(bucket_name, file_key)
        reader = csv.DictReader(data, delimiter=",")
        apps = AppointmentsList(appointments=reader)
        new_patients = {}
        patient_trips = {}
        with Appointment.batch_write() as batch:
            for app in apps.appointments:
                trips = patient_trips.get(app.patient_number, {})
                if (
                    patient_mapping.get(app.patient_number)
                    and not trips
                    and not patient_trips.get(app.patient_number)
                ):
                    trips = Via().get_trips(patient_mapping.get(app.patient_number))
                    patient_trips[app.patient_number] = trips
                location = f"{app.location_name},{app.location_street1},{app.location_street2},{app.location_city},{app.location_state},{app.location_zip}".replace(
                    ",,", ","
                )
                appointment_datetime = app.appointment_datetime.replace(tzinfo=central_tz).astimezone(utc_tz)
                appointment = Appointment(
                    id=app.appointment_id,
                    patient_id=app.patient_number,
                    patient_name=f"{app.patient_first_name} {app.patient_middle_initial} {app.patient_last_name}",
                    location=location,
                    start_time=appointment_datetime,
                    end_time=appointment_datetime
                    + timedelta(minutes=app.appointment_duration),
                    status=app.status,
                    provider="veradigm",
                    ride=self.get_matching_ride(
                        location,
                        trips.get("trips", []),
                        int(appointment_datetime.timestamp()),
                    )
                    or VIA_RIDE_MOCK,
                )
                new_patients[appointment.patient_id] = appointment.patient_name
                batch.save(appointment)
        with FTPLogs.batch_write() as batch:
            batch.save(
                FTPLogs(
                    name=file_key, server_last_modified=int(last_modified.timestamp())
                )
            )
        with Patient.batch_write() as batch:
            for patient_id, patient_name in new_patients.items():
                batch.save(
                    Patient(
                        name=patient_name, patient_id=patient_id, provider="veradigm"
                    )
                )

    def process_all(self, patient_mapping):
        print("Processing all appointments")
        patient_trips = {}
        appointment_objs = []
        for appointment in Appointment.scan(
            filter_condition=(Appointment.end_time >= datetime.now(timezone.utc))
            & (Appointment.status == "Booked")
        ):
            if rider_id := patient_mapping["all"].get(appointment.patient_id):
                print("rider_id:",rider_id)
                start_time = int(appointment.start_time.timestamp())
                trips = patient_trips.get(appointment.patient_id)
                if trips is None:
                    trips = Via().get_trips(rider_id)
                    patient_trips[appointment.patient_id] = trips
                existing_ride = getattr(appointment, "ride", {}) or {}
                new_ride = (
                    self.get_matching_ride(
                        appointment.location, trips.get("trips", []), start_time
                    )
                    or VIA_RIDE_MOCK
                )
                if (
                    existing_ride 
                    and new_ride 
                    and existing_ride.get("trip_id") 
                    and new_ride.get("trip_id") 
                    and existing_ride["trip_id"] == new_ride["trip_id"]
                ):
                    
                    if "driver_info" not in new_ride and "driver_info" in existing_ride:
                        new_ride["driver_info"] = existing_ride["driver_info"]
                    if "vehicle_info" not in new_ride and "vehicle_info" in existing_ride:
                        new_ride["vehicle_info"] = existing_ride["vehicle_info"]
                appointment.ride = new_ride
                appointment_objs.append(appointment)
        with Appointment.batch_write() as batch:
            for appointment in appointment_objs:
                batch.save(appointment)

    def __call__(self, event, context, *args, **kwargs):
        patient_mapping = self.get_patient_mapping()
        if records := event.get("Records", []):
            s3_event = records[0]["s3"]
            bucket_name = s3_event["bucket"]["name"]
            file_key = s3_event["object"]["key"]
            # Veradigm pushes SFTP
            self.veradigm_with_via(
                patient_mapping, bucket_name=bucket_name, file_key=file_key
            )
        elif detail_type := event.get("detail-type", ""):
            if detail_type == "Scheduled Event":
                self.epic_with_via(patient_mapping)
                self.process_all(patient_mapping)


class AppointmentsMapperWithViaMock(AppointmentsMapperWithVia):

    def epic_with_via(self, patient_mapping):
        patient_trips = {}
        appointment_objs = []
        for appointment in Appointment.scan(
            filter_condition=(Appointment.end_time >= datetime.now(timezone.utc))
            & (Appointment.status == "Booked")
        ):
            if rider_id := patient_mapping["epic"].get(appointment.patient_id):
                start_time = int(appointment.start_time.timestamp())
                trips = patient_trips.get(appointment.patient_id)
                if trips is None:
                    trips = Via().get_trips(rider_id)
                    patient_trips[appointment.patient_id] = trips
                existing_ride = getattr(appointment, "ride", {}) or {}
                new_ride = (
                    self.get_matching_ride(
                        appointment.location, trips.get("trips", []), start_time
                    )
                    or VIA_RIDE_MOCK
                )
                if (
                    existing_ride 
                    and new_ride 
                    and existing_ride.get("trip_id") 
                    and new_ride.get("trip_id") 
                    and existing_ride["trip_id"] == new_ride["trip_id"]
                ):
                    if "driver_info" not in new_ride and "driver_info" in existing_ride:
                        new_ride["driver_info"] = existing_ride["driver_info"]
                    if "vehicle_info" not in new_ride and "vehicle_info" in existing_ride:
                        new_ride["vehicle_info"] = existing_ride["vehicle_info"]
                appointment.ride = new_ride
                appointment_objs.append(appointment)
        with Appointment.batch_write() as batch:
            for appointment in appointment_objs:
                batch.save(appointment)


def data_populator(event, context, **kwargs):
    print(event, context)
    if MOCK_DATA:
        AppointmentsMapperWithViaMock()(event, context)
    else:
        AppointmentsMapperWithVia()(event, context)


if __name__ == "__main__":
    data_populator()
