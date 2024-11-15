from typing import Any, Callable

from health_connector_base.constants import STRINGS
from health_connector_base.exceptions import ValidationError
from health_connector_base.location_manager import LocationManager
from pynamodb.attributes import UnicodeAttribute, UTCDateTimeAttribute


class ChoiceUnicodeAttribute(UnicodeAttribute):
    def __init__(
        self,
        choices: tuple,
        hash_key: bool = False,
        range_key: bool = False,
        null: bool | None = None,
        default: str | Callable[..., str] | None = None,
        default_for_new: Any | Callable[..., str] | None = None,
        attr_name: str | None = None,
    ) -> None:

        self.choices = choices
        super().__init__(hash_key, range_key, null, default, default_for_new, attr_name)

    def serialize(self, value: Any) -> Any:
        if value not in self.choices:
            raise ValidationError(STRINGS["CHOICE_INVALID"] % {"value": value})
        return value


class CustomUTCDateTimeAttribute(UTCDateTimeAttribute):
    def serialize(self, value):
        if isinstance(value, str):
            value = self._fast_parse_utc_date_string(value)
        return super(CustomUTCDateTimeAttribute, self).serialize(value)


class AddressAttribute(UnicodeAttribute):
    def serialize(self, value: Any) -> Any:
        if not LocationManager().is_valid_address(value):
            raise ValidationError(STRINGS["INVALID_ADDRESS"])
        return value
