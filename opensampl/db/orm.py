"""Main openSAMPL database ORM"""

import uuid
from datetime import datetime
from typing import Any, Optional

from geoalchemy2 import Geometry, WKTElement
from geoalchemy2.shape import to_shape
from loguru import logger
from sqlalchemy import TIMESTAMP, Boolean, Column, Float, ForeignKey, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.event import listens_for
from sqlalchemy.orm import Session, declarative_base, relationship
from sqlalchemy.schema import MetaData

SCHEMA_NAME = "castdb"


class BaseHelpers:
    """
    Mixin for Base class that adds some helper methods.

    Provides common functionality for database models including serialization,
    constraint handling, and reference resolution.
    """

    def to_dict(self):
        """
        Convert to dictionary, including changes to make it serializable.

        Returns:
            Dictionary representation of the object with serializable values.

        """

        def convert_value(value: Any) -> Any:
            if isinstance(value, datetime):
                return value.isoformat()
            if hasattr(value, "__geo_interface__"):
                return to_shape(value).__geo_interface__
            return value

        return {c.name: convert_value(getattr(self, c.name)) for c in self.__table__.columns}

    @classmethod
    def identifiable_constraint(cls) -> Optional[str]:
        """
        Get the name of the unique constraint used for identification.

        Used in cases where we want to use a unique constraint to overwrite other entries.
        Primarily used for probe metadata, so that we can use probe_key and ip_address to change name,
        which is also a unique constraint, without manually retrieving the uuid from the db.

        Returns:
            Name of the unique constraint, or None if not applicable.

        """
        return None

    def resolve_references(self, session: Optional[Session] = None) -> None:  # noqa: ARG002
        """
        Resolve UUIDs for other entries in the database given a unique constraint.

        Primarily used for probe metadata, so that we can use location_name and test_name to resolve to UUIDs.

        Args:
            session: Database session to use for resolution.

        """
        return

    def get_session(self) -> Session:
        """
        Extract session from object, raise runtime error if not found.

        Returns:
            Database session associated with this object.

        Raises:
            RuntimeError: If no session is found for this object.

        """
        session = Session.object_session(self)
        if not session:
            raise RuntimeError("No session found for this object")
        return session


Base = declarative_base(cls=BaseHelpers, metadata=MetaData(schema=SCHEMA_NAME))


# --- SUPPORTED TABLES ----


class Locations(Base):
    """
    Table for storing locations

    Automatically parses lat, lon, and z into point
    """

    __tablename__ = "locations"

    uuid = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Auto generated primary key UUID for the location",
    )
    name = Column(Text, unique=True, nullable=False, comment="Unique name identifying the location")
    geom = Column(Geometry(geometry_type="GEOMETRY", srid=4326), comment="Geospatial point geometry (lat, lon, z)")
    public = Column(Boolean, nullable=True, comment="Whether this location is publicly visible")

    probe_metadata = relationship("ProbeMetadata")

    def __init__(self, **kwargs: dict):
        """
        Initialize Location object, including converting lat, lon, and z into point.

        Args:
            **kwargs: Keyword arguments including lat, lon, z, and projection for geometry.

        """
        if "lat" in kwargs and "lon" in kwargs:
            lat = kwargs.pop("lat")
            lon = kwargs.pop("lon")
            z = kwargs.pop("z", None)
            projection = int(kwargs.pop("projection", 4326))
            point_str = f"POINT({lon} {lat} {z})" if z is not None else f"POINT({lon} {lat})"
            kwargs["geom"] = WKTElement(point_str, srid=projection)
        super().__init__(**kwargs)


class TestMetadata(Base):
    """TestMetadata table for storing name, start and end of tests"""

    __tablename__ = "test_metadata"

    uuid = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Auto generated primary key UUID for the test",
    )
    name = Column(Text, unique=True, nullable=False, comment="Unique name of the test")
    start_date = Column(TIMESTAMP, comment="Start timestamp of the test")
    end_date = Column(TIMESTAMP, comment="End timestamp of the test")

    probe_metadata = relationship("ProbeMetadata")


class ProbeMetadata(Base):
    """
    Stores the basic information about clock probes.

    A unique probe is identified by its ip address and probe_id.

    Can be associated with an existing location or test by its name by providing location_name/test_name
    """

    __tablename__ = "probe_metadata"

    uuid = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Auto generated primary key UUID for the probe metadata entry",
    )
    probe_id = Column(Text, comment="Interface ID of the probe device; can be multiple probes from the same ip_address")
    ip_address = Column(Text, comment="IP address of the probe")
    vendor = Column(Text, comment="Manufacturer/vendor of the probe")
    model = Column(Text, comment="Model name/number of the probe")
    name = Column(Text, unique=True, comment="Human-readable name for the probe")
    public = Column(Boolean, nullable=True, comment="Whether this probe is publicly visible")
    location_uuid = Column(String(36), ForeignKey("locations.uuid"), comment="Foreign key to the associated location")
    test_uuid = Column(String(36), ForeignKey("test_metadata.uuid"), comment="Foreign key to the associated test")

    __table_args__ = (UniqueConstraint("probe_id", "ip_address", name="uq_probe_metadata_ipaddress_probeid"),)

    probe_data = relationship("ProbeData")
    adva_metadata = relationship("AdvaMetadata", back_populates="probe", uselist=False)

    # --- CUSTOM PROBE METADATA RELATIONSHIP ---

    def __init__(self, **kwargs: Any):
        """
        Initialize Probe Metadata object, dealing with converting location name into uuid.

        Args:
            **kwargs: Keyword arguments including location_name and test_name for reference resolution.

        """
        location_name = kwargs.pop("location_name", None)
        test_name = kwargs.pop("test_name", None)
        super().__init__(**kwargs)

        if location_name:
            self._location_name = location_name  # Store it temporarily until we have a session
        if test_name:
            self._test_name = test_name

    @classmethod
    def identifiable_constraint(cls) -> Optional[str]:
        """
        Get the name of the unique constraint used for identification.

        Returns:
            Name of the unique constraint for probe metadata.

        """
        return "uq_probe_metadata_ipaddress_probeid"

    def resolve_references(self, session: Optional[Session] = None):
        """
        Resolve references to location and/or test entries when given just the name.

        Provides the correct foreign UUID key by looking up the location or test by name.

        Args:
            session: SQLAlchemy session, used to query for the location/test.

        """
        if not session:
            try:
                session = self.get_session()
            except RuntimeError:
                logger.warning(
                    "No session found for this object, and no session provided to resolve_references. "
                    "Will not resolve references."
                )
                return

        if hasattr(self, "_location_name"):
            location = session.query(Locations).filter_by(name=self._location_name).first()
            if not location:
                logger.warning(
                    f"Could not find location with name {self._location_name}, leaving location reference null."
                )
            self.location_uuid = location.uuid if location else None
            delattr(self, "_location_name")  # Clean up after resolving

        if hasattr(self, "_test_name"):
            test_meta = session.query(TestMetadata).filter_by(name=self._test_name).first()
            if not test_meta:
                logger.warning(
                    f"Could not find test metadata with name {self._test_name}, leaving test reference null."
                )
            self.test_uuid = test_meta.uuid if test_meta else None
            delattr(self, "_test_name")


class ProbeData(Base):
    """
    Table for storing actual time data from the probes.

    Each entry has a reference to the probe's uuid, timestamp for the measurement, and value for the measurement.
    """

    __tablename__ = "probe_data"

    time = Column(TIMESTAMP, primary_key=True, comment="Timestamp of the measurement")
    probe_uuid = Column(
        String(36),
        ForeignKey("probe_metadata.uuid"),
        primary_key=True,
        comment="Foreign key to the probe that collected the data",
    )
    reference_uuid = Column(
        String(36),
        ForeignKey("reference.uuid"),
        primary_key=True,
        comment="Foreign key to the reference point for the reading",
    )
    metric_type_uuid = Column(
        String(36),
        ForeignKey("metric_type.uuid"),
        primary_key=True,
        comment="Foreign key to the metric type being measured",
    )
    value = Column(JSONB, comment="Measurement value stored as JSON; value's expected type defined via metric")


class MetricType(Base):
    """
    The  type of metric that is being recorded in probe_data

    Stores a required value type (as in, string, int, float) and a unit (as in seconds, ppm, etc).
    Optionally identify it with a name and a description.
    """

    __tablename__ = "metric_type"
    uuid = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Auto generated primary key UUID for the metric type",
    )
    name = Column(String, unique=True, comment="Unique name for the metric type (e.g., phase offset, delay, quality)")
    description = Column(Text, nullable=True, comment="Optional human-readable description of the metric")
    unit = Column(String, nullable=False, comment="Measurement unit (e.g., ns, s, ppm)")
    value_type = Column(
        String, nullable=False, default="string", comment="Data type of the value (e.g., float, int, string)"
    )


class Reference(Base):
    """
    Table for storing reference information.

    These references are what the recorded values in Probe Data are against. Types of reference are determined by
    metric type
    """

    __tablename__ = "reference"
    uuid = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Auto generated primary key UUID for the reference entry",
    )
    reference_type_uuid = Column(
        String(36),
        ForeignKey("reference_type.uuid"),
        comment="Foreign key to the reference type (e.g., GPS, GNSS, Probe)",
    )
    compound_reference_uuid = Column(
        String(36),
        nullable=True,
        comment=(
            "Optional foreign key if the reference type is Compound. Which table it references is determined via "
            "reference_table field in reference_type table"
        ),
    )
    __table_args__ = (
        UniqueConstraint("reference_type_uuid", "compound_reference_uuid", name="uq_ref_type_uuid_cnstr"),
    )


class ReferenceType(Base):
    """Stores the types of reference that can be used in the reference table."""

    __tablename__ = "reference_type"

    uuid = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        comment="Auto generated primary key UUID for the reference type",
    )
    name = Column(
        String, unique=True, nullable=False, comment="Unique name of the reference type (e.g., GPS, GNSS, Unknown)"
    )
    description = Column(Text, nullable=True, comment="Optional human-readable description of the reference type")
    reference_table = Column(
        String, nullable=True, comment="Optional table name if the reference type is a compound type"
    )


class AdvaMetadata(Base):
    """
    ADVA Clock Probe specific metadata

    This is metadata that is specifically provided by ADVA probes in their text file exports.
    """

    __tablename__ = "adva_metadata"

    probe_uuid = Column(
        String, ForeignKey("probe_metadata.uuid"), primary_key=True, comment="Foreign key to the associated probe"
    )
    type = Column(Text, comment="ADVA measurement type (eg Phase)")
    start = Column(TIMESTAMP, comment="Start time for the current measurement series")
    frequency = Column(Integer, comment="Sampling frequency of the ADVA probe, in rate per second")
    timemultiplier = Column(Integer, comment="Time multiplier used by the ADVA tool")
    multiplier = Column(Integer, comment="Data scaling multiplier")
    title = Column(Text)
    adva_probe = Column(Text)
    adva_reference = Column(Text)
    adva_reference_expected_ql = Column(Text)
    adva_source = Column(Text)
    adva_direction = Column(Text)
    adva_version = Column(Float)
    adva_status = Column(Text)
    adva_mtie_mask = Column(Text)
    adva_mask_margin = Column(Integer)
    additional_metadata = Column(
        JSONB, comment="Additional metadata found in the file headers that did not match existing columns"
    )

    probe = relationship("ProbeMetadata", back_populates="adva_metadata")


class Defaults(Base):
    """Table for storing the default uuid for lookup tables"""

    __tablename__ = "defaults"

    table_name = Column(Text, primary_key=True, comment="Name of the table/category this entry belongs to")
    uuid = Column(String(36), nullable=False, comment="Optional UUID reference resolved from name_value")


class MicrochipTWSTMetadata(Base):
    """
    Microchip TWST Clock Probe specific metadata

    This is metadata that is specifically provided by microchip twst probes in their text file exports.
    """

    __tablename__ = "microchip_twst_metadata"

    probe_uuid = Column(
        String, ForeignKey("probe_metadata.uuid"), primary_key=True, comment="Foreign key to the associated probe"
    )
    additional_metadata = Column(
        JSONB, comment="Additional metadata found in the file headers that did not match existing columns"
    )


# --- CUSTOM TABLES ---      !! Do not remove line, used as reference when inserting metadata table


# --- TABLE FUNCTIONS ---


@listens_for(ProbeMetadata, "before_insert")
def resolve_uuid(mapper, connection, target: ProbeMetadata):  # noqa: ARG001,ANN001
    """
    Resolve the location_uuid and test_uuid entries for a probe before the object is inserted into the database.

    Args:
        mapper: SQLAlchemy mapper object.
        connection: Database connection.
        target: ProbeMetadata instance being inserted.

    """
    session = Session.object_session(target)
    if session:
        target.resolve_references(session)


@listens_for(ProbeData, "before_insert")
def set_probe_data_defaults(mapper, connection, target: ProbeData):  # noqa: ARG001,ANN001
    """
    Set default values for reference_uuid and metric_type_uuid before inserting ProbeData.

    Uses the database function get_default_uuid_for() to retrieve default UUIDs
    when the values are not explicitly provided.

    Args:
        mapper: SQLAlchemy mapper object.
        connection: Database connection.
        target: ProbeData instance being inserted.

    """
    try:
        session = Session.object_session(target)

        if session is None:
            raise RuntimeError("No session could be resolved from target")  # noqa: TRY301

        # Set default reference_uuid if not provided
        if target.reference_uuid is None:
            result = session.execute(text("SELECT get_default_uuid_for('reference')")).scalar()
            target.reference_uuid = str(result)

        # Set default metric_type_uuid if not provided
        if target.metric_type_uuid is None:
            result = session.execute(text("SELECT get_default_uuid_for('metric_type')")).scalar()
            target.metric_type_uuid = str(result)

    except Exception as e:
        logger.warning(f"Failed to set default values for ProbeData: {e}")
        # Continue without setting defaults rather than failing the insert


def get_table_names():
    """
    Get all table names from the ORM in opensampl.db.orm.

    Returns:
        List of table names sorted by dependency order.

    """
    return [table.name for table in Base.metadata.sorted_tables]
