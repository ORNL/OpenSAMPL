"""Main openSAMPL database ORM"""

import uuid
from datetime import datetime
from typing import Any

from geoalchemy2 import Geometry, WKTElement
from geoalchemy2.shape import to_shape
from loguru import logger
from sqlalchemy import NUMERIC, TIMESTAMP, Boolean, Column, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.event import listens_for
from sqlalchemy.orm import Session, declarative_base, relationship
from sqlalchemy.schema import MetaData

SCHEMA_NAME = "castdb"


class BaseHelpers:
    """Mixin for Base class that adds some helper methods"""

    def to_dict(self):
        """Convert to dictionary, including changes to make it serializable"""

        def convert_value(value: Any) -> Any:
            if isinstance(value, datetime):
                return value.isoformat()
            if hasattr(value, "__geo_interface__"):
                return to_shape(value).__geo_interface__
            return value

        return {c.name: convert_value(getattr(self, c.name)) for c in self.__table__.columns}


Base = declarative_base(cls=BaseHelpers, metadata=MetaData(schema=SCHEMA_NAME))


class Locations(Base):
    """
    Table for storing locations

    Automatically parses lat, lon, and z into point
    """

    __tablename__ = "locations"

    uuid = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(Text, unique=True, nullable=False)
    geom = Column(Geometry(geometry_type="GEOMETRY", srid=4326))
    public = Column(Boolean, nullable=True)

    probe_metadata = relationship("ProbeMetadata")

    def __init__(self, **kwargs: dict):
        """Initialize Location object, including converting lat, lon, and z into point"""
        if "lat" in kwargs and "lon" in kwargs:
            lat = kwargs.pop("lat")
            lon = kwargs.pop("lon")
            z = kwargs.pop("z", None)
            projection = kwargs.pop("projection", 4326)
            point_str = f"POINT({lon} {lat} {z})" if z is not None else f"POINT({lon} {lat})"
            kwargs["geom"] = WKTElement(point_str, srid=projection)
        super().__init__(**kwargs)


class TestMetadata(Base):
    """TestMetadata table for storing name, start and end of tests"""

    __tablename__ = "test_metadata"

    uuid = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(Text, unique=True, nullable=False)
    start_date = Column(TIMESTAMP)
    end_date = Column(TIMESTAMP)

    probe_metadata = relationship("ProbeMetadata")


class ProbeMetadata(Base):
    """
    Stores the basic information about clock probes.

    A unique probe is identified by its ip address and probe_id.

    Can be associated with an existing location or test by its name by providing location_name/test_name
    """

    __tablename__ = "probe_metadata"

    uuid = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    probe_id = Column(Text)
    ip_address = Column(Text)
    vendor = Column(Text)
    model = Column(Text)
    name = Column(Text, unique=True)
    public = Column(Boolean, nullable=True)
    location_uuid = Column(String(36), ForeignKey("locations.uuid"))
    test_uuid = Column(String(36), ForeignKey("test_metadata.uuid"))

    __table_args__ = (UniqueConstraint("probe_id", "ip_address", name="uq_probe_metadata_ipaddress_probeid"),)

    probe_data = relationship("ProbeData")
    adva_metadata = relationship("AdvaMetadata", back_populates="probe", uselist=False)

    def __init__(self, **kwargs: dict):
        """Initialize Probe Metadata object, dealing with converting location name into uuid"""
        location_name = kwargs.pop("location_name", None)
        test_name = kwargs.pop("test_name", None)
        super().__init__(**kwargs)

        if location_name:
            self._location_name = location_name  # Store it temporarily until we have a session
        if test_name:
            self._test_name = test_name

    def resolve_references(self, session: Session = None):
        """
        Resolve references.

        Resolve the references to location and/or test entries when given just the name, and
        provides the correct foreign uuid key.

        :param session: sqlalchemy session, used to query for the location/test
        """
        if not session:  # If no session, attempt to figure it out from the object
            session = Session.object_session(self)
            if not session:
                logger.warning(
                    "No session provided and one could not be found. Not resolving references for probe metadata."
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

    time = Column(TIMESTAMP, primary_key=True)
    probe_uuid = Column(String(36), ForeignKey("probe_metadata.uuid"), primary_key=True)
    value = Column(NUMERIC)


class AdvaMetadata(Base):
    """
    ADVA Clock Probe specific metadata

    This is metadata that is specifically provided by ADVA probes in their text file exports.
    """

    __tablename__ = "adva_metadata"

    probe_uuid = Column(String, ForeignKey("probe_metadata.uuid"), primary_key=True)
    type = Column(Text)
    start = Column(TIMESTAMP)
    frequency = Column(Integer)
    timemultiplier = Column(Integer)
    multiplier = Column(Integer)
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

    probe = relationship("ProbeMetadata", back_populates="adva_metadata")


@listens_for(ProbeMetadata, "before_insert")
def resolve_uuid(mapper, connection, target: ProbeMetadata):  # noqa: ARG001,ANN001
    """Resolve the location_uuid and test_uuid entries for a probe before the object is inserted into the database."""
    session = Session.object_session(target)
    if session:
        target.resolve_references(session)
