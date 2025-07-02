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

    def get_parser(self):
        """Get the Python Class object associated with the vendor type"""
        module = __import__(
            f"opensampl.vendors.{self.parser_module}",
            fromlist=[self.parser_class],
            globals=globals(),
        )
        return getattr(module, self.parser_class)

    def get_orm(self):
        """Get the Sqlalchemy ORM object associated with the vendor type"""
        module = __import__("opensampl.db.orm", fromlist=[self.metadata_orm], globals=globals())
        return getattr(module, self.metadata_orm)


class VENDORS:
    """Vendors available for use"""

    # --- SUPPORTED VENDORS ----
    ADVA = VendorType(
        name="ADVA",
        parser_class="AdvaProbe",
        parser_module="adva",
        metadata_table="adva_metadata",
        metadata_orm="AdvaMetadata",
    )

    MICROCHIP_TWST = VendorType(
        name="MicrochipTWST",
        parser_class="MicrochipTWSTProbe",
        parser_module="microchip.twst",
        metadata_table="microchip_twst_metadata",
        metadata_orm="MicrochipTWSTMetadata",
    )

    # --- CUSTOM VENDORS ---      !! Do not remove line, used as reference when inserting vendor

    # --- VENDOR FUNCTIONS ---

    @classmethod
    def all(cls) -> list[VendorType]:
        """Get all vendors"""
        return [attr for attr in cls.__dict__.values() if isinstance(attr, VendorType)]

    @classmethod
    def get_by_name(cls, name: str, case_sensitive: bool = False) -> VendorType:
        """
        Get a vendor type by name

        Args:
            name: The name of the vendor to get
            case_sensitive: Whether to match the name case-sensitively (default: False)

        Returns:
            VendorType: The vendor type definition

        """
        for attr_name in dir(cls):
            if attr_name.startswith("_"):
                continue

            attr = getattr(cls, attr_name)
            if isinstance(attr, VendorType):
                vendor_name = attr.name
                if vendor_name == name or (not case_sensitive and vendor_name.lower() == name.lower()):
                    return attr

        raise ValueError(f"Vendor '{name}' not found")
