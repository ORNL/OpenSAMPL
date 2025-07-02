"""Class for openSAMPL References"""

from pydantic import BaseModel, field_validator

from opensampl.db.orm import get_table_names


class ReferenceType(BaseModel):
    """Class for managing Reference Types"""

    name: str
    description: str


class CompoundReferenceType(ReferenceType):
    """Class for managing Reference Types which Reference another Table"""

    reference_table: str

    @field_validator("reference_table", mode="after")
    @classmethod
    def table_exists(cls, value: str) -> str:
        """Validate reference table exists in db"""
        if value not in get_table_names():
            raise ValueError(f"Table {value} does not exist in ORM")
        return value


class REF_TYPES:  # noqa: N801
    """Class for storing the reference types as they appear in the db for easy access"""

    # --- SUPPORTED REFERENCE TYPES ---
    GPS = ReferenceType(name="GPS", description="Global Positioning System (GPS) reference")
    GNSS = ReferenceType(name="GNSS", description="Global Navigation Satellite System (GNSS) reference")
    UNKNOWN = ReferenceType(name="UNKNOWN", description="Reference type is unknown")
    PROBE = CompoundReferenceType(
        name="PROBE",
        description="Reference is another clock probe",
        reference_table="probe_metadata",
    )

    # --- CUSTOM REFERENCE TYPES ---      !! Do not remove line, used as reference when inserting reference type
