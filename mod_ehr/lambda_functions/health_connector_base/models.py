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

class Appointment(BaseModel):
    id = UnicodeAttribute(hash_key=True, default_for_new=lambda: str(uuid.uuid4()))
    patient_id = UnicodeAttribute()
    patient_name = UnicodeAttribute()
    location = AddressAttribute()
    start_time = UTCDateTimeAttribute()
    end_time = UTCDateTimeAttribute()
    status = UnicodeAttribute()
    provider = ChoiceUnicodeAttribute(choices=["epic", "veradigm"], default="epic")
    ride = JSONAttribute(default=lambda: VIA_RIDE_MOCK)
    patient_id_index = PatientIdIndex()

    class Meta:
        table_name = "appointment_table"


class Patient(BaseModel):
    patient_id = UnicodeAttribute(hash_key=True)
    name = UnicodeAttribute()
    via_rider_id = UnicodeAttribute(null=True, default="")
    provider = ChoiceUnicodeAttribute(choices=["epic", "veradigm"], default="epic")

    class Meta:
        table_name = "patients_table"


class Settings(BaseModel):
    name = UnicodeAttribute(hash_key=True)
    value = UnicodeAttribute()

    class Meta:
        table_name = "settings_table"


class FTPLogs(BaseModel):
    name = UnicodeAttribute(hash_key=True)
    server_last_modified = NumberAttribute()

    class Meta:
        table_name = "ftp_logs_table"
