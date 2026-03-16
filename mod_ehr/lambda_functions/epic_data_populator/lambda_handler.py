from datetime import datetime, timedelta, timezone
from health_connector_base.models import Appointment, Hospital, Patient
from health_connector_base.smart_epic import JWTHelper, SmartEpicClient
from health_connector_base.secrets_manager import KMSClient

class AppointmentsMapperWithEpic:

    def _get_jwt(self, credentials):
        """
        Generates a JWT token.
        Returns:
            The generated JWT token.
        """

        return JWTHelper(
            client_id=credentials["epic_client_id"],
            private_key=credentials["epic_private_key"].replace("\\n", "\n"),
            jwks_url=credentials["epic_jwks_url"],
            jwks_kid=credentials["epic_jwks_kid"],
        ).generate_jwt()
    
    def get_patient_mapping_for_hospital(self, hospital_id: str) -> dict:
        """
        Returns the patient-rider mapping for a specific hospital.
        This assumes the Patient model has a `hospital_id` attribute.
        """
        return {
            patient.patient_id: patient.via_rider_id
            for patient in Patient.scan(
                (Patient.provider == "epic") & (Patient.hospital_id == hospital_id) & (Patient.via_rider_id.exists())
            )
        }
        
    def _map_participant_data_location(self, appointment: dict, smart_client: SmartEpicClient, patient_id: str) -> dict:
        result = {}
        for participant in appointment["participant"]:
            participant_type = participant["actor"]["reference"]["@value"].split("/")
            if participant_type[0] == "Location":
                if location_response := smart_client.get_location_data(
                    participant_type[-1]
                ):
                    result["location"] = location_response

        #getting patient info
        patient_info = smart_client.get_patient_info(patient_id)
        first_name = ""
        last_name = ""
        patient_phone_no = {}
        patient_email = {}
        for name_part in patient_info["Patient"]["name"]:
            if name_part["use"]["@value"] == "usual":
                if len(name_part["given"])>1:
                    first_name = " ".join([_["@value"] for _ in name_part["given"]])
                else:
                    first_name = name_part["given"]["@value"]
                last_name = name_part["family"]["@value"]
                break
        for contact_part in patient_info["Patient"]["telecom"]:
            if contact_part["system"]["@value"] == "phone":
                if ( not patient_phone_no.get(contact_part["value"]["@value"])) or (patient_phone_no.get(contact_part["value"]["@value"]) and int(contact_part.get("rank",{}).get("@value","")) < int(patient_phone_no[contact_part["value"]["@value"]])):
                    patient_phone_no[contact_part["value"]["@value"]] = int(contact_part.get("rank",{}).get("@value","999"))
                else:
                    continue
            elif contact_part["system"]["@value"] == "email":
                if ( not patient_email.get(contact_part["value"]["@value"])) or (patient_email.get(contact_part["value"]["@value"]) and int(contact_part.get("rank",{}).get("@value","")) < int(patient_email[contact_part["value"]["@value"]])):
                    patient_email[contact_part["value"]["@value"]] = int(contact_part.get("rank",{}).get("@value","999"))
                else:
                    continue
            patient_phone_no = dict(sorted(patient_phone_no.items(), key = lambda x: x[1], reverse=False))
            patient_email = dict(sorted(patient_email.items(), key = lambda x: x[1], reverse=False))
            result["patient_first_name"] = first_name
            result["patient_last_name"] = last_name
            result["patient_phone_no"] = str(list(patient_phone_no.keys())) if patient_phone_no else ""
            result["patient_email"] = str(list(patient_email.keys())) if patient_email else ""
            result["patient_id"] = patient_id
            result["patient_name"] = f"{first_name} {last_name}"
        return result

    def fetch_epic_data(self, patient_mapping: dict, hospital, credentials):
        print("fetch_epic_data called")
        print("hospital:",hospital)
        smart_client = SmartEpicClient(self._get_jwt(credentials))
        appointment_objs = []
        print("Fetching Epic data for patients:", patient_mapping)
        for patient_id, rider_id in patient_mapping.items():
            print("patient_id:", patient_id, rider_id)
            if appointments := smart_client.get_appointments(patient_id):
                print("Fetched appointments for patient_id:", patient_id, "->", appointments)
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
                            "hospital_id": hospital.id,
                        # } | self._map_participants_data(appointment, smart_client)
                        } | self._map_participant_data_location(appointment, smart_client, patient_id)
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

    def __call__(self, event, context, *args, **kwargs):
        print("AppointmentsMapperWithEpic invoked")

        if event.get("detail-type") != "Scheduled Event":
            print("Not a scheduled event, skipping.")
            return

        secrets_manager = KMSClient()
        epic_hospitals = Hospital.scan(Hospital.provider == 'epic')

        for hospital in epic_hospitals:
            try:
                print(f"Processing hospital: {hospital.id} ({hospital.name})")

                credentials = secrets_manager.get_hospital_secret(hospital.id)
                required_keys = ['epic_client_id', 'epic_private_key', 'epic_jwks_url', 'epic_jwks_kid']
                if not all(k in credentials for k in required_keys):
                    print(f"Skipping hospital {hospital.id}: Missing one or more required Epic credentials in Secrets Manager.")
                    continue

                patient_mapping = self.get_patient_mapping_for_hospital(hospital.id)

                if not patient_mapping:
                    print(f"No epic patients with via_rider_id found for hospital {hospital.id}")
                    continue

                self.fetch_epic_data(patient_mapping, hospital, credentials)
            except Exception as e:
                print(f"Failed to process hospital {hospital.id} ({hospital.name}). Error: {e}")
                continue

def data_populator(event, context, **kwargs):
    print("epic_data_populator triggered")
    AppointmentsMapperWithEpic()(event, context)