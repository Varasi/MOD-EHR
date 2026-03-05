import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

from health_connector_base.constants import VIA_RIDE_MOCK
from health_connector_base.custom_attributes import (
    AddressAttribute,
    ChoiceUnicodeAttribute,
)
from health_connector_base.custom_attributes import (
    CustomUTCDateTimeAttribute as UTCDateTimeAttribute,
)
from pynamodb.attributes import JSONAttribute, NumberAttribute, UnicodeAttribute
from pynamodb.expressions.condition import Condition
from pynamodb.models import MetaModel, Model
from pynamodb.indexes import GlobalSecondaryIndex, AllProjection


class CustomMeta(MetaModel):

    def __new__(cls, name, bases, namespace, discriminator=None):
        if "Meta" in namespace and hasattr(namespace["Meta"], "table_name"):
            namespace["Meta"].table_name = (
                f"{os.environ.get('ENVIRONMENT','development').lower()}_{namespace['Meta'].table_name}"
            )
        return super().__new__(cls, name, bases, namespace)


class BaseModel(Model, metaclass=CustomMeta):
    created = UTCDateTimeAttribute(default_for_new=datetime.now(timezone.utc))
    modified = UTCDateTimeAttribute(default=datetime.now(timezone.utc))

    def save(
        self, condition: Condition | None = None, *, add_version_condition: bool = True
    ) -> Dict[str, Any]:
        self.modified = datetime.now(timezone.utc)
        return super(BaseModel, self).save(
            condition, add_version_condition=add_version_condition
        )

class PatientIdIndex(GlobalSecondaryIndex):
    """
    GSI where the partition key is patient_id
    """
    class Meta:
        index_name = "patient_id-index"     # Name shown in DynamoDB Console
        projection = AllProjection()        # Return all attributes

    patient_id = UnicodeAttribute(hash_key=True)

class AppointmentsByHospitalsIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "hospital_id-end_time-index"
        projection = AllProjection()

    hospital_id = UnicodeAttribute(hash_key=True)
    end_time = UTCDateTimeAttribute(range_key=True)

class Appointment(BaseModel):
    id = UnicodeAttribute(hash_key=True, default_for_new=lambda: str(uuid.uuid4()))
    hospital_id = UnicodeAttribute()
    patient_id = UnicodeAttribute()
    patient_name = UnicodeAttribute()
    location = AddressAttribute()
    start_time = UTCDateTimeAttribute()
    end_time = UTCDateTimeAttribute()
    status = UnicodeAttribute()
    provider = ChoiceUnicodeAttribute(choices=["epic", "veradigm"], default="epic")
    ride = JSONAttribute(default=lambda: VIA_RIDE_MOCK)
    patient_id_index = PatientIdIndex()
    appointments_by_hospitals = AppointmentsByHospitalsIndex()
    patient_first_name = UnicodeAttribute(null=True, default="")
    patient_last_name = UnicodeAttribute(null=True, default="")
    patient_phone_no = UnicodeAttribute(null=True, default="")
    patient_email = UnicodeAttribute(null=True, default="")

    class Meta:
        table_name = "appointment_table"


class HospitalIdIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "hospital_id-index"
        projection = AllProjection()

    hospital_id = UnicodeAttribute(hash_key=True)


class Patient(BaseModel):
    patient_id = UnicodeAttribute(hash_key=True)
    name = UnicodeAttribute()
    via_rider_id = UnicodeAttribute(null=True, default="")
    provider = ChoiceUnicodeAttribute(choices=["epic", "veradigm"], default="epic")
    hospital_id = UnicodeAttribute()
    
    hospital_id_index = HospitalIdIndex()

    class Meta:
        table_name = "patients_table"

class SettingsByHospitalIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "hospital_id-index"
        projection = AllProjection()

    hospital_id = UnicodeAttribute(hash_key=True)
    name = UnicodeAttribute(range_key=True)

class Settings(BaseModel):
    name = UnicodeAttribute(hash_key=True)
    value = UnicodeAttribute()
    hospital_id = UnicodeAttribute(range_key=True)
    settings_by_hospital = SettingsByHospitalIndex()

    class Meta:
        table_name = "settings_table"

class FTPLogsByHospitalIndex(GlobalSecondaryIndex):
    class Meta:
        index_name = "hospital_id-index"
        projection = AllProjection()

    hospital_id = UnicodeAttribute(hash_key=True)
    name = UnicodeAttribute(range_key=True)

class FTPLogs(BaseModel):
    name = UnicodeAttribute(hash_key=True)
    server_last_modified = NumberAttribute()
    hospital_id = UnicodeAttribute(range_key=True)
    logs_by_hospital = FTPLogsByHospitalIndex()

    class Meta:
        table_name = "ftp_logs_table"

class Hospital(BaseModel):
    id = UnicodeAttribute(hash_key=True)
    name = UnicodeAttribute()
    subdomain = UnicodeAttribute()
    status = UnicodeAttribute()
    timezone = UnicodeAttribute(default="CT")
    location = AddressAttribute()
    provider = ChoiceUnicodeAttribute(choices=["epic", "veradigm"], default="epic")
    epic_client_id = UnicodeAttribute(null=True, default=None)
    epic_private_key = UnicodeAttribute(null=True, default=None)
    epic_jwks_url = UnicodeAttribute(null=True, default=None)
    epic_jwks_kid = UnicodeAttribute(null=True, default=None)
    s3_subfolder_name = UnicodeAttribute(null=True, default=None)
    sftp_username = UnicodeAttribute(null=True, default=None)
    sftp_password = UnicodeAttribute(null=True, default=None)


    class Meta:
        table_name = "hospitals_table"
