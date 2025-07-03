"""Functions and objects for managing openSAMPL Metric Types"""

from typing import Any, Union

from pydantic import BaseModel, field_serializer, field_validator

type_map = {"int": int, "float": float, "str": str, "bool": bool, "list": list, "dict": dict, "jsonb": object}


class MetricType(BaseModel):
    """Object for defining different metric types"""

    name: str
    description: str
    unit: str
    value_type: type

    def convert_to_type(self, value: Any) -> Any:
        """Convert a given value to the expected type for the Metric"""
        return self.value_type(value)

    @field_serializer("value_type")
    def serialize_type(self, value: type):
        """Return the name of value_type for serializing"""
        return value.__name__

    @field_validator("value_type", mode="before")
    @classmethod
    def validate_type(cls, value: Union[str, type]) -> Any:
        """Ensure the value_type field is converted to a type if provided as a string"""
        if isinstance(value, str):
            value = value.strip()
            if value in type_map:
                return type_map[value]
        return value


class METRICS:
    """Class for storing metric types"""

    # --- SUPPORTED METRICS ----
    PHASE_OFFSET = MetricType(
        name="Phase Offset",
        description="Difference in seconds between the probe's time reading and the reference time reading",
        unit="s",
        value_type=float,
    )
    EB_NO = MetricType(
        name="Eb/No",
        description=(
            "Energy per bit to noise power spectral density ratio measured at the clock probe. "
            "Indicates the quality of the received signal relative to noise."
        ),
        unit="dB",
        value_type=float,
    )
    UNKNOWN = MetricType(
        name="UNKNOWN",
        description="Unknown or unspecified metric type, with value_type of jsonb due to flexibility",
        unit="unknown",
        value_type=object,
    )

    # --- CUSTOM METRICS ---      !! Do not remove line, used as reference when inserting metric
