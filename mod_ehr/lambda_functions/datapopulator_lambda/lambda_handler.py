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
from health_connector_base.models import Appointment, FTPLogs, Patient, Settings, Hospital
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

    def get_prior_period(self, hospital_id: str):
        with contextlib.suppress(Settings.DoesNotExist):
            return int(Settings.get(hospital_id, "prior_period").value) * 60
        return DIFF_MATCH_IN_SEC

    def get_subsequent_period(self, hospital_id: str):
        with contextlib.suppress(Settings.DoesNotExist):
            return int(Settings.get(hospital_id, "subsequent_period").value) * -60
        return -900

    def get_patient_mapping(self) -> dict:
        """
        Returns the patient-rider mapping as a dictionary.
        Returns:
            dict: The patient-rider mapping.
        """

        return {
            "epic": {
                (patient.hospital_id, patient.patient_id): patient.via_rider_id
                for patient in Patient.scan(
                    filter_condition=(
                        Patient.via_rider_id.exists() & (Patient.provider == "epic")
                    )
                )
            },
            "veradigm": {
                (patient.hospital_id, patient.patient_id): patient.via_rider_id
                for patient in Patient.scan(
                    filter_condition=(
                        Patient.via_rider_id.exists() & (Patient.provider == "veradigm")
                    )
                )
            },
            "all": {
                (patient.hospital_id, patient.patient_id): patient.via_rider_id
                for patient in Patient.scan(
                    filter_condition=(Patient.via_rider_id.exists())
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
        self, address: str, trips: list, appointment_start_time: int, hospital_id: str
    ) -> dict:
        """
        Returns the to-appointment matching ride: the trip whose dropoff_eta is
        closest to appointment_start_time and whose dropoff location is within
        LOCATION_DIFF km of the appointment address.
        """
        match_ride = {}
        prev_diff = 1e9
        prev_location_diff = 1e9
        prior_period = self.get_prior_period(hospital_id)
        subsequent_period = self.get_subsequent_period(hospital_id)
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
            print(f"subsequent_period: {subsequent_period}, cur_diff: {cur_diff}, prior_period: {prior_period}")
            print(f"cur_diff: {cur_diff}, prev_diff: {prev_diff}, cur_location_diff: {cur_location_diff}, prev_location_diff: {prev_location_diff}")
            if (
                subsequent_period <= cur_diff <= prior_period
                and cur_diff < prev_diff
                and cur_location_diff <= LOCATION_DIFF
                and cur_location_diff <= prev_location_diff
            ):
                prev_diff = cur_diff
                match_ride = trip
                prev_location_diff = cur_location_diff
        print("Matched to-appointment ride:", match_ride)
        return match_ride

    def get_matching_return_ride(
        self, address: str, trips: list, appointment_end_time: int, hospital_id: str
    ) -> dict:
        """
        Returns the from-appointment matching ride: the trip whose pickup_eta is
        closest to appointment_end_time and whose pickup location is within
        LOCATION_DIFF km of the appointment address.
        """
        match_ride = {}
        prev_diff = 1e9
        prev_location_diff = 1e9
        prior_period = self.get_prior_period(hospital_id)
        subsequent_period = self.get_subsequent_period(hospital_id)
        for trip in trips:
            # Positive diff means pickup is after end_time (patient leaves after appt ends)
            cur_diff = int(trip["pickup_eta"] - appointment_end_time)
            cur_location_diff = int(
                LocationManager().get_distance_from_address_coords(
                    address,
                    [
                        trip.get("pickup", {}).get("lat", 0),
                        trip.get("pickup", {}).get("lng", 0),
                    ],
                )
            )
            print(f"[return] subsequent_period: {subsequent_period}, cur_diff: {cur_diff}, prior_period: {prior_period}")
            print(f"[return] cur_diff: {cur_diff}, prev_diff: {prev_diff}, cur_location_diff: {cur_location_diff}, prev_location_diff: {prev_location_diff}")
            if (
                subsequent_period <= cur_diff <= prior_period
                and cur_diff < prev_diff
                and cur_location_diff <= LOCATION_DIFF
                and cur_location_diff <= prev_location_diff
            ):
                prev_diff = cur_diff
                match_ride = trip
                prev_location_diff = cur_location_diff
        print("Matched from-appointment ride:", match_ride)
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
        for (hospital_id, patient_key), rider_id in patient_mapping["epic"].items():
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
                            "hospital_id": hospital_id,
                        } | self._map_participants_data(appointment, smart_client)
                        # result |= {
                        #     "ride": self.get_matching_ride(
                        #         result["location"], trips, int(start_time.timestamp()), hospital_id
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
        if "/" not in file_key:
            print(f"Skipping file {file_key} as it is not in a subfolder")
            return

        subfolder = file_key.split("/")[0]
        hospital_id = None
        for hospital in Hospital.scan(Hospital.s3_subfolder_name == subfolder):
            hospital_id = hospital.id
            break

        if not hospital_id:
            print(f"No hospital found for subfolder {subfolder}")
            return

        data, last_modified = self.get_file_data(bucket_name, file_key)
        reader = csv.DictReader(data, delimiter=",")
        apps = AppointmentsList(appointments=reader)
        new_patients = {}
        patient_trips = {}
        with Appointment.batch_write() as batch:
            for app in apps.appointments:
                trips = patient_trips.get(app.patient_number, {})
                rider_id = patient_mapping["veradigm"].get((hospital_id, app.patient_number))
                if (
                    rider_id
                    and not trips
                    and not patient_trips.get(app.patient_number)
                ):
                    trips = Via().get_trips(rider_id)
                    patient_trips[app.patient_number] = trips
                location = f"{app.location_name},{app.location_street1},{app.location_street2},{app.location_city},{app.location_state},{app.location_zip}".replace(
                    ",,", ","
                )
                appointment_datetime = app.appointment_datetime.replace(tzinfo=central_tz).astimezone(utc_tz)
                appointment_end_datetime = appointment_datetime + timedelta(minutes=app.appointment_duration)
                trip_list = trips.get("trips", [])
                to_ride = (
                    self.get_matching_ride(
                        location,
                        trip_list,
                        int(appointment_datetime.timestamp()),
                        hospital_id,
                    )
                    or VIA_RIDE_MOCK["to_appointment"]
                )
                from_ride = (
                    self.get_matching_return_ride(
                        location,
                        trip_list,
                        int(appointment_end_datetime.timestamp()),
                        hospital_id,
                    )
                    or VIA_RIDE_MOCK["from_appointment"]
                )
                appointment = Appointment(
                    id=app.appointment_id,
                    patient_id=app.patient_number,
                    patient_name=f"{app.patient_first_name} {app.patient_middle_initial} {app.patient_last_name}",
                    location=location,
                    start_time=appointment_datetime,
                    end_time=appointment_end_datetime,
                    status=app.status,
                    provider="veradigm",
                    ride={"to_appointment": to_ride, "from_appointment": from_ride},
                    hospital_id=hospital_id,
                )
                new_patients[appointment.patient_id] = appointment.patient_name
                batch.save(appointment)
        with FTPLogs.batch_write() as batch:
            batch.save(
                FTPLogs(
                    name=file_key, server_last_modified=int(last_modified.timestamp()), hospital_id=hospital_id
                )
            )
        with Patient.batch_write() as batch:
            for patient_id, patient_name in new_patients.items():
                batch.save(
                    Patient(
                        name=patient_name,
                        patient_id=patient_id,
                        provider="veradigm",
                        hospital_id=hospital_id,
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
            hospital_id = getattr(appointment, 'hospital_id', None)
            if rider_id := patient_mapping["all"].get((hospital_id, appointment.patient_id)):
                print("rider_id:",rider_id)
                start_time = int(appointment.start_time.timestamp())
                trips = patient_trips.get(appointment.patient_id)
                if trips is None:
                    trips = Via().get_trips(rider_id)
                    patient_trips[appointment.patient_id] = trips
                end_time = int(appointment.end_time.timestamp())
                trip_list = trips.get("trips", [])
                existing_ride = getattr(appointment, "ride", {}) or {}

                new_to_ride = (
                    self.get_matching_ride(
                        appointment.location, trip_list, start_time, hospital_id
                    )
                    or VIA_RIDE_MOCK["to_appointment"]
                )
                new_from_ride = (
                    self.get_matching_return_ride(
                        appointment.location, trip_list, end_time, hospital_id
                    )
                    or VIA_RIDE_MOCK["from_appointment"]
                )

                # Preserve driver/vehicle info when the matched trip hasn't changed.
                # Handle both the new structured format and legacy flat-ride records.
                existing_to = existing_ride.get("to_appointment", existing_ride)
                existing_from = existing_ride.get("from_appointment", {})

                if (
                    existing_to.get("trip_id")
                    and new_to_ride.get("trip_id")
                    and existing_to["trip_id"] == new_to_ride["trip_id"]
                ):
                    if "driver_info" not in new_to_ride and "driver_info" in existing_to:
                        new_to_ride["driver_info"] = existing_to["driver_info"]
                    if "vehicle_info" not in new_to_ride and "vehicle_info" in existing_to:
                        new_to_ride["vehicle_info"] = existing_to["vehicle_info"]

                if (
                    existing_from.get("trip_id")
                    and new_from_ride.get("trip_id")
                    and existing_from["trip_id"] == new_from_ride["trip_id"]
                ):
                    if "driver_info" not in new_from_ride and "driver_info" in existing_from:
                        new_from_ride["driver_info"] = existing_from["driver_info"]
                    if "vehicle_info" not in new_from_ride and "vehicle_info" in existing_from:
                        new_from_ride["vehicle_info"] = existing_from["vehicle_info"]

                appointment.ride = {
                    "to_appointment": new_to_ride,
                    "from_appointment": new_from_ride,
                }
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
            hospital_id = getattr(appointment, 'hospital_id', None)
            if rider_id := patient_mapping["epic"].get((hospital_id, appointment.patient_id)):
                start_time = int(appointment.start_time.timestamp())
                end_time = int(appointment.end_time.timestamp())
                trips = patient_trips.get(appointment.patient_id)
                if trips is None:
                    trips = Via().get_trips(rider_id)
                    patient_trips[appointment.patient_id] = trips
                trip_list = trips.get("trips", [])
                existing_ride = getattr(appointment, "ride", {}) or {}

                new_to_ride = (
                    self.get_matching_ride(
                        appointment.location, trip_list, start_time, hospital_id
                    )
                    or VIA_RIDE_MOCK["to_appointment"]
                )
                new_from_ride = (
                    self.get_matching_return_ride(
                        appointment.location, trip_list, end_time, hospital_id
                    )
                    or VIA_RIDE_MOCK["from_appointment"]
                )

                existing_to = existing_ride.get("to_appointment", existing_ride)
                existing_from = existing_ride.get("from_appointment", {})

                if (
                    existing_to.get("trip_id")
                    and new_to_ride.get("trip_id")
                    and existing_to["trip_id"] == new_to_ride["trip_id"]
                ):
                    if "driver_info" not in new_to_ride and "driver_info" in existing_to:
                        new_to_ride["driver_info"] = existing_to["driver_info"]
                    if "vehicle_info" not in new_to_ride and "vehicle_info" in existing_to:
                        new_to_ride["vehicle_info"] = existing_to["vehicle_info"]

                if (
                    existing_from.get("trip_id")
                    and new_from_ride.get("trip_id")
                    and existing_from["trip_id"] == new_from_ride["trip_id"]
                ):
                    if "driver_info" not in new_from_ride and "driver_info" in existing_from:
                        new_from_ride["driver_info"] = existing_from["driver_info"]
                    if "vehicle_info" not in new_from_ride and "vehicle_info" in existing_from:
                        new_from_ride["vehicle_info"] = existing_from["vehicle_info"]

                appointment.ride = {
                    "to_appointment": new_to_ride,
                    "from_appointment": new_from_ride,
                }
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
