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
    NTP_DELAY = MetricType(
        name="NTP Delay",
        description="Round-trip delay (RTT) to the NTP server or observed path delay in seconds",
        unit="s",
        value_type=float,
    )
    NTP_JITTER = MetricType(
        name="NTP Jitter",
        description=(
            "Jitter or offset variation for NTP in seconds (true value from chrony/ntpq when available; "
            "remote single-packet collection may use a delay/dispersion bound estimate)"
        ),
        unit="s",
        value_type=float,
    )
    NTP_STRATUM = MetricType(
        name="NTP Stratum",
        description="NTP stratum level (distance from reference clock)",
        unit="level",
        value_type=float,
    )
    NTP_REACHABILITY = MetricType(
        name="NTP Reachability",
        description="NTP reachability register (0-255) as a scalar for plotting",
        unit="count",
        value_type=float,
    )
    NTP_DISPERSION = MetricType(
        name="NTP Dispersion",
        description="Combined error budget / dispersion in seconds",
        unit="s",
        value_type=float,
    )
    NTP_ROOT_DELAY = MetricType(
        name="NTP Root Delay",
        description="Root delay from NTP packet or local estimate in seconds",
        unit="s",
        value_type=float,
    )
    NTP_ROOT_DISPERSION = MetricType(
        name="NTP Root Dispersion",
        description="Root dispersion from NTP packet or local estimate in seconds",
        unit="s",
        value_type=float,
    )
    NTP_POLL_INTERVAL = MetricType(
        name="NTP Poll Interval",
        description="Poll interval in seconds",
        unit="s",
        value_type=float,
    )
    NTP_SYNC_HEALTH = MetricType(
        name="NTP Sync Health",
        description="1.0 if synchronized/healthy, 0.0 otherwise (probe-defined)",
        unit="ratio",
        value_type=float,
    )

    # --- CUSTOM METRICS ---      !! Do not remove line, used as reference when inserting metric
