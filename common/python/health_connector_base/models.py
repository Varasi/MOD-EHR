import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict

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


class Appointment(BaseModel):
    id = UnicodeAttribute(hash_key=True, default_for_new=lambda: str(uuid.uuid4()))
    patient_id = UnicodeAttribute()
    patient_name = UnicodeAttribute()
    location = AddressAttribute()
    start_time = UTCDateTimeAttribute()
    end_time = UTCDateTimeAttribute()
    status = ChoiceUnicodeAttribute(choices=["Booked", "Pending", "Cancelled"])
    provider = ChoiceUnicodeAttribute(choices=["epic", "veradigm"], default="epic")

    class Meta:
        table_name = "appointment_table"


class Dashboard(BaseModel):
    id = UnicodeAttribute(hash_key=True)
    patient_id = UnicodeAttribute()
    patient_name = UnicodeAttribute()
    location = UnicodeAttribute()
    status = ChoiceUnicodeAttribute(choices=["Booked", "Pending", "Cancelled"])
    start_time = NumberAttribute()
    end_time = NumberAttribute()
    provider = ChoiceUnicodeAttribute(choices=["epic", "veradigm"], default="epic")
    ride = JSONAttribute()

    class Meta:
        table_name = "dashboard_table"


class Patient(BaseModel):
    via_rider_id = UnicodeAttribute(hash_key=True)
    name = UnicodeAttribute()
    epic_id = UnicodeAttribute()

    class Meta:
        table_name = "patients_table"


class Settings(BaseModel):
    name = UnicodeAttribute(hash_key=True)
    value = UnicodeAttribute()

    class Meta:
        table_name = "settings_table"
