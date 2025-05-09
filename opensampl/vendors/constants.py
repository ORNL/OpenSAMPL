"""Defines constants for use in probe functions"""

from pydantic import BaseModel


class ProbeKey(BaseModel):
    """Model for Probe identity, which is both probe_id and ip_address"""

    probe_id: str
    ip_address: str

    def __repr__(self):
        """Represent Probe key as [ip_address]_[probe_id]"""
        return f"{self.ip_address}_{self.probe_id}"

    def __str__(self):
        """Get Probe key string as [ip_address]_[probe_id]"""
        return self.__repr__()


class VendorType(BaseModel):
    """Model for Vendor Type Definition"""

    name: str
    parser_class: str
    parser_module: str
    metadata_table: str
    metadata_orm: str


ADVA = VendorType(
    name="ADVA",
    parser_class="AdvaProbe",
    parser_module="adva",
    metadata_table="adva_metadata",
    metadata_orm="AdvaMetadata",
)

VENDOR_MAP = {
    "ADVA": ADVA,
}


def get_vendor_parser(name: str):
    """Given a vendor name string, get the VendorType definition"""
    if name not in VENDOR_MAP:
        raise AttributeError(f"Unknown vendor: {name}")

    vendor_type = VENDOR_MAP[name]
    module = __import__(
        f"opensampl.vendors.{vendor_type.parser_module}",
        fromlist=[vendor_type.parser_class],
        globals=globals(),
    )
    return getattr(module, vendor_type.parser_class)


def get_vendor_orm(name: str):
    """Given a vendor name string, get the vendor's metadata ORM model"""
    if name not in VENDOR_MAP:
        raise AttributeError(f"Unknown vendor: {name}")

    vendor_type = VENDOR_MAP[name]
    module = __import__("opensampl.db.orm", fromlist=[vendor_type.metadata_orm], globals=globals())
    return getattr(module, vendor_type.metadata_orm)
