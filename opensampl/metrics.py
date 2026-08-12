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
    ALTITUDE_HAE = MetricType(
        name="Altitude HAE",
        description="Altitude above the reference ellipsoid",
        unit="m",
        value_type=float,
    )
    ALTITUDE_MSL = MetricType(
        name="Altitude MSL",
        description="Altitude above mean sea level",
        unit="m",
        value_type=float,
    )
    ANTENNA_STATUS = MetricType(
        name="Antenna Status",
        description="Receiver antenna status code",
        unit="code",
        value_type=int,
    )
    ANTENNA_POWER_STATUS = MetricType(
        name="Antenna Power Status",
        description="Receiver antenna power status code",
        unit="code",
        value_type=int,
    )
    CLIMB_RATE = MetricType(
        name="Climb Rate",
        description="Positive climb or negative sink rate",
        unit="m/s",
        value_type=float,
    )
    CLOCK_BIAS = MetricType(
        name="Clock Bias",
        description="Offset of the local GNSS clock relative to UTC",
        unit="ns",
        value_type=float,
    )
    CLOCK_DRIFT = MetricType(
        name="Clock Drift",
        description="Rate at which the local GNSS clock is drifting",
        unit="ns/s",
        value_type=float,
    )
    DATUM = MetricType(
        name="Datum",
        description="Geodetic datum used by the receiver",
        unit="name",
        value_type=str,
    )
    DEPTH = MetricType(
        name="Depth",
        description="Reported depth, typically below the keel",
        unit="m",
        value_type=float,
    )
    DGPS_AGE = MetricType(
        name="DGPS Age",
        description="Age of differential GNSS correction data",
        unit="s",
        value_type=float,
    )
    DGPS_STATION = MetricType(
        name="DGPS Station",
        description="Identifier of the differential GNSS station",
        unit="id",
        value_type=int,
    )
    ECEF_X = MetricType(
        name="ECEF X",
        description="Earth-centered, Earth-fixed X position",
        unit="m",
        value_type=float,
    )
    ECEF_Y = MetricType(
        name="ECEF Y",
        description="Earth-centered, Earth-fixed Y position",
        unit="m",
        value_type=float,
    )
    ECEF_Z = MetricType(
        name="ECEF Z",
        description="Earth-centered, Earth-fixed Z position",
        unit="m",
        value_type=float,
    )
    ECEF_POSITION_ERROR = MetricType(
        name="ECEF Position Error",
        description="Estimated Earth-centered, Earth-fixed position error",
        unit="m",
        value_type=float,
    )
    ECEF_VELOCITY_X = MetricType(
        name="ECEF Velocity X",
        description="Earth-centered, Earth-fixed X velocity",
        unit="m/s",
        value_type=float,
    )
    ECEF_VELOCITY_Y = MetricType(
        name="ECEF Velocity Y",
        description="Earth-centered, Earth-fixed Y velocity",
        unit="m/s",
        value_type=float,
    )
    ECEF_VELOCITY_Z = MetricType(
        name="ECEF Velocity Z",
        description="Earth-centered, Earth-fixed Z velocity",
        unit="m/s",
        value_type=float,
    )
    ECEF_VELOCITY_ERROR = MetricType(
        name="ECEF Velocity Error",
        description="Estimated Earth-centered, Earth-fixed velocity error",
        unit="m/s",
        value_type=float,
    )
    CLIMB_ERROR = MetricType(
        name="Climb Error",
        description="Estimated climb-rate error",
        unit="m/s",
        value_type=float,
    )
    TRACK_ERROR = MetricType(
        name="Track Error",
        description="Estimated track-direction error",
        unit="degrees",
        value_type=float,
    )
    HORIZONTAL_POSITION_ERROR = MetricType(
        name="Horizontal Position Error",
        description="Estimated horizontal two-dimensional position error",
        unit="m",
        value_type=float,
    )
    SPEED_ERROR = MetricType(
        name="Speed Error",
        description="Estimated speed error",
        unit="m/s",
        value_type=float,
    )
    LONGITUDE_ERROR = MetricType(
        name="Longitude Error",
        description="Estimated longitude error",
        unit="m",
        value_type=float,
    )
    LATITUDE_ERROR = MetricType(
        name="Latitude Error",
        description="Estimated latitude error",
        unit="m",
        value_type=float,
    )
    VERTICAL_ERROR = MetricType(
        name="Vertical Error",
        description="Estimated vertical position error",
        unit="m",
        value_type=float,
    )
    GEOID_SEPARATION = MetricType(
        name="Geoid Separation",
        description="Difference between the reference ellipsoid and mean sea level",
        unit="m",
        value_type=float,
    )
    JAMMING_INDICATOR = MetricType(
        name="Jamming Indicator",
        description="Receiver jamming severity indicator",
        unit="level",
        value_type=int,
    )
    LATITUDE = MetricType(
        name="Latitude",
        description="Geodetic latitude, positive north and negative south",
        unit="degrees",
        value_type=float,
    )
    LEAP_SECONDS = MetricType(
        name="Leap Seconds",
        description="Current UTC leap-second offset known to the receiver",
        unit="s",
        value_type=int,
    )
    LONGITUDE = MetricType(
        name="Longitude",
        description="Geodetic longitude, positive east and negative west",
        unit="degrees",
        value_type=float,
    )
    MAGNETIC_TRACK = MetricType(
        name="Magnetic Track",
        description="Course over ground relative to magnetic north",
        unit="degrees",
        value_type=float,
    )
    MAGNETIC_VARIATION = MetricType(
        name="Magnetic Variation",
        description="Magnetic declination, positive west and negative east",
        unit="degrees",
        value_type=float,
    )
    RELATIVE_POSITION_DOWN = MetricType(
        name="Relative Position Down",
        description="Down component of the relative position vector",
        unit="m",
        value_type=float,
    )
    RELATIVE_POSITION_EAST = MetricType(
        name="Relative Position East",
        description="East component of the relative position vector",
        unit="m",
        value_type=float,
    )
    RELATIVE_POSITION_NORTH = MetricType(
        name="Relative Position North",
        description="North component of the relative position vector",
        unit="m",
        value_type=float,
    )
    SPHERICAL_POSITION_ERROR = MetricType(
        name="Spherical Position Error",
        description="Estimated three-dimensional spherical position error",
        unit="m",
        value_type=float,
    )
    SPEED = MetricType(
        name="Speed",
        description="Speed over ground",
        unit="m/s",
        value_type=float,
    )
    FIX_STATUS = MetricType(
        name="Fix Status",
        description="GNSS fix-status code reported by the receiver",
        unit="code",
        value_type=int,
    )
    RECEIVER_TEMPERATURE = MetricType(
        name="Receiver Temperature",
        description="GNSS receiver temperature",
        unit="degrees Celsius",
        value_type=float,
    )
    TRACK = MetricType(
        name="Track",
        description="Course over ground relative to true north",
        unit="degrees",
        value_type=float,
    )
    VELOCITY_DOWN = MetricType(
        name="Velocity Down",
        description="Down component of receiver velocity",
        unit="m/s",
        value_type=float,
    )
    VELOCITY_EAST = MetricType(
        name="Velocity East",
        description="East component of receiver velocity",
        unit="m/s",
        value_type=float,
    )
    VELOCITY_NORTH = MetricType(
        name="Velocity North",
        description="North component of receiver velocity",
        unit="m/s",
        value_type=float,
    )
    WIND_ANGLE_MAGNETIC = MetricType(
        name="Wind Angle Magnetic",
        description="Wind angle relative to magnetic north",
        unit="degrees",
        value_type=float,
    )
    WIND_ANGLE_RELATIVE = MetricType(
        name="Wind Angle Relative",
        description="Wind angle relative to the platform",
        unit="degrees",
        value_type=float,
    )
    WIND_ANGLE_TRUE = MetricType(
        name="Wind Angle True",
        description="Wind angle relative to true north",
        unit="degrees",
        value_type=float,
    )
    WIND_SPEED_RELATIVE = MetricType(
        name="Wind Speed Relative",
        description="Wind speed relative to the platform",
        unit="m/s",
        value_type=float,
    )
    WIND_SPEED_TRUE = MetricType(
        name="Wind Speed True",
        description="True wind speed",
        unit="m/s",
        value_type=float,
    )
    WATER_TEMPERATURE = MetricType(
        name="Water Temperature",
        description="Reported water temperature",
        unit="degrees Celsius",
        value_type=float,
    )

    # --- CUSTOM METRICS ---      !! Do not remove line, used as reference when inserting metric
