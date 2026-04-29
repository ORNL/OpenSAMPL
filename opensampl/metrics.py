"""Functions and objects for managing openSAMPL Metric Types"""

from __future__ import annotations

from typing import Any

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
    def validate_type(cls, value: str | type) -> Any:
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
    DELAY = MetricType(
        name="Delay",
        description=(
            "Round-trip delay (RTD) or Round-Trip Time (RTT). The time in seconds it takes for a data signal to "
            "travel from a source to a destination and back, including acknowledgement."
        ),
        unit="s",
        value_type=float,
    )
    JITTER = MetricType(
        name="Jitter",
        description=("Jitter or offset variation in delay in seconds. Represents inconsistent response times."),
        unit="s",
        value_type=float,
    )
    STRATUM = MetricType(
        name="Stratum",
        description=(
            'Stratum level. Hierarchical layer defining the distance (or "hops") between device and reference.'
        ),
        unit="level",
        value_type=int,
    )
    REACHABILITY = MetricType(
        name="Reachability",
        description=(
            "Reachability register (0-255) as a scalar for plotting. Ability of a source node to communicate "
            "with a target node."
        ),
        unit="count",
        value_type=float,
    )
    DISPERSION = MetricType(
        name="Dispersion",
        description="Uncertainty in a clock's time relative to its reference source in seconds",
        unit="s",
        value_type=float,
    )
    NTP_ROOT_DELAY = MetricType(
        name="NTP Root Delay",
        description=(
            "Total round-trip network delay from the local system"
            " all the way to the primary reference clock (stratum 0)"
        ),
        unit="s",
        value_type=float,
    )
    NTP_ROOT_DISPERSION = MetricType(
        name="NTP Root Dispersion",
        description="The total accumulated clock uncertainty from the local system back to the primary reference clock",
        unit="s",
        value_type=float,
    )
    POLL_INTERVAL = MetricType(
        name="Poll Interval",
        description="Time between requests sent to a time server in seconds",
        unit="s",
        value_type=float,
    )
    SYNC_HEALTH = MetricType(
        name="Sync Health",
        description="1.0 if synchronized/healthy, 0.0 otherwise (probe-defined)",
        unit="ratio",
        value_type=float,
    )

    # --- CUSTOM METRICS ---      !! Do not remove line, used as reference when inserting metric
