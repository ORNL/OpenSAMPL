"""
Creating new vendors/clock probe types based on config files.

This module provides functionality to create new vendor types for the openSAMPL
package based on YAML configuration files. It handles the generation of probe
classes, metadata classes, and updates to the constants file.

Note:
    This module is in beta and may change in future versions.

"""

from pathlib import Path
from string import Template
from typing import Any, Optional, Union

import yaml
from loguru import logger
from pydantic import BaseModel, Field, model_validator

from opensampl.create.insert_markers import INSERT_MARKERS, InsertMarker
from opensampl.vendors.constants import VendorType


class MetadataField(BaseModel):
    """
    Definition for a metadata field in the vendor config.

    Attributes:
        name: The name of the metadata field.
        sqlalchemy_type: The SQLAlchemy type for the field (default: "Text").
        primary_key: Whether this field is a primary key (default: False).

    """

    name: str
    sqlalchemy_type: Optional[str] = Field(default="Text")
    primary_key: Optional[bool] = False


class DEFAULT_METADATA:  # noqa N801
    """Default metadata fields for vendor configurations."""

    ADDITIONAL_FIELDS = MetadataField(name="additional_metadata", sqlalchemy_type="JSONB")

    @classmethod
    def get_default_fields(cls) -> list[MetadataField]:
        """
        Get list of default metadata fields.

        Returns:
            List of MetadataField instances for default fields.

        """
        return [v for k, v in cls.__dict__.items() if not k.startswith("_")]


class VendorConfig(VendorType):
    """
    Configuration definition for a new vendor type.

    Attributes:
        base_path: Base path for the openSAMPL package.

    """

    base_path: Path = Path(__file__).parent.parent

    @classmethod
    def from_config_file(cls, config_path: Union[str, Path]) -> "VendorConfig":
        """
        Convert file config into Config object.

        Args:
            config_path: Path to the YAML configuration file.

        Returns:
            VendorConfig instance created from the file.

        """
        if isinstance(config_path, str):
            config_path = Path(config_path)
        config = yaml.safe_load(config_path.read_text())
        return cls(**config)

    @model_validator(mode="before")
    @classmethod
    def generate_default_fields(cls, data: Any) -> Any:
        """
        Generate default values for fields if they are not provided in the config.

        Args:
            data: Raw configuration data.

        Returns:
            Updated configuration data with default values.

        """
        if not isinstance(data, dict):
            return data

        name = data.get("name")
        if not name:
            return data

        # Generate default values if not provided
        if not data.get("metadata_table"):
            data["metadata_table"] = f"{name.lower()}_metadata"

        if not data.get("metadata_orm"):
            data["metadata_orm"] = f"{name.capitalize()}Metadata"

        if not data.get("parser_class"):
            data["parser_class"] = f"{name.capitalize()}Probe"

        if not data.get("parser_module"):
            data["parser_module"] = f"{name.lower()}"

        fields = []
        metadata_fields = data.get("metadata_fields")
        if isinstance(metadata_fields, list) and (len(metadata_fields) > 0 and isinstance(metadata_fields[0], dict)):
            for field in metadata_fields:
                if field.get("type", None) is not None:
                    fields.append(MetadataField(name=field.get("name"), sqlalchemy_type=field.get("type")))
                else:
                    fields.append(MetadataField(name=field.get("name")))
        else:
            logger.warning(
                "Metadata fields defaulting to probe uuid and freeform json: additional metadata. Either metadata "
                "fields not provided or were malformed. "
            )
        fields.extend(DEFAULT_METADATA.get_default_fields())
        data["metadata_fields"] = fields
        return data

    def create_probe_file(self) -> Path:
        """
        Create a new probe class file.

        Returns:
            Path to the created probe file.

        """
        # Create the probe file
        probe_file = self.base_path / "vendors" / f"{self.parser_module}.py"
        # TODO in write time data, optionally add value_str to df ensure maximum precision when sending through backend.

        template_file = Path(__file__).parent / "templates" / "parser_template.txt"
        content = Template(template_file.read_text()).safe_substitute(
            name=self.name, upper_name=self.parser_class.upper(), parser_class=self.parser_class
        )

        probe_file.write_text(content)
        logger.warning(
            f"Wrote {self.parser_class} to {probe_file}. Open the file, and follow TODO instructions to implement."
        )
        return probe_file

    def generate_metadata_columns(self) -> str:
        """
        Generate the metadata column definitions for the ORM template.

        Returns:
            String containing formatted column definitions.

        """
        columns = [f"    {field.name} = Column({field.sqlalchemy_type})" for field in self.metadata_fields]
        return "\n".join(columns)

    def create_metadata_class(self) -> str:
        """
        Create the metadata class using template-based approach.

        Returns:
            String containing the ORM class definition.

        """
        template_file = Path(__file__).parent / "templates" / "orm_metadata.txt"
        metadata_columns = self.generate_metadata_columns()

        return Template(template_file.read_text()).safe_substitute(
            metadata_orm=self.metadata_orm,
            metadata_table=self.metadata_table,
            metadata_columns=metadata_columns,
            name_lower=self.name.lower(),
        )

    @staticmethod
    def insert_content_at_marker(marker: InsertMarker, content: str) -> None:
        """
        Insert content at a specified marker in a file.

        Args:
            marker: InsertMarker defining where to insert content.
            content: Content to insert at the marker location.

        """
        target_file = marker.filepath
        output_lines = []
        inserted = False

        for line in target_file.read_text().splitlines():
            output_lines.append(line)
            if not inserted and marker.comment_marker in line:
                output_lines.append(content)
                inserted = True

        if not inserted:
            logger.warning(f"Marker '{marker.comment_marker}' not found in {target_file}")
            return

        target_file.write_text("\n".join(output_lines))
        logger.info(f"Content inserted at marker in {target_file}")

    def create_orm_class(self):
        """Create the ORM metadata class in the database ORM file."""
        orm_content = self.create_metadata_class()
        self.insert_content_at_marker(INSERT_MARKERS.ORM_CLASS, orm_content)
        logger.info(f"Created ORM class {self.metadata_orm} in database")

    def update_constants(self):
        """Update the constants.py file with the new vendor type."""
        template_file = INSERT_MARKERS.VENDOR.template_path
        content = Template(template_file.read_text()).safe_substitute(
            upper_name=self.parser_class.upper(),
            name=self.name,
            parser_class=self.parser_class,
            parser_module=self.parser_module,
            metadata_table=self.metadata_table,
            metadata_orm=self.metadata_orm,
        )
        self.insert_content_at_marker(INSERT_MARKERS.VENDOR, content)

    def create(self):
        """Create the new vendor by generating probe file, ORM class, and updating constants."""
        self.create_probe_file()
        self.create_orm_class()
        self.update_constants()
