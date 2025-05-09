"""
**beta**

 Creating new vendors/clock probe types based on config files
"""

import ast
from pathlib import Path
from typing import Any, Optional, Union

import yaml
from loguru import logger
from pydantic import BaseModel, Field, model_validator

from opensampl.helpers.source_writer import OrmClassFormatter
from opensampl.vendors.constants import VendorType


class MetadataField(BaseModel):
    """Definition for a metadata field in the vendor config"""

    name: str
    sqlalchemy_type: Optional[str] = Field(default="Text", alias="type")
    primary_key: Optional[bool] = False


class VendorConfig(VendorType):
    """Configuration definition for a new vendor type"""

    metadata_fields: list[MetadataField]
    base_path: Path = Path(__file__).parent.parent

    @classmethod
    def from_config_file(cls, config_path: Union[str, Path]) -> "VendorConfig":
        """Convert file config into Config object"""
        if isinstance(config_path, str):
            config_path = Path(config_path)
        config = yaml.safe_load(config_path.read_text())
        return cls(**config)

    @model_validator(mode="before")
    @classmethod
    def generate_default_fields(cls, data: Any) -> Any:
        """Generate default values for fields if they are not provided in the config"""
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

        metadata_fields = data.get("metadata_fields")
        if not metadata_fields or not isinstance(metadata_fields, dict):
            return data

        fields = []
        for field, sql_type in metadata_fields.items():
            if sql_type:
                fields.append(MetadataField(name=field, type=sql_type))
            else:
                fields.append(MetadataField(name=field))
        data["metadata_fields"] = fields
        return data

    def create_probe_file(self) -> Path:
        """Create a new probe class file."""
        # Create the probe file
        probe_file = self.base_path / "vendors" / f"{self.parser_module}.py"
        # TODO in write time data, optionally add value_str to df ensure maximum precision when sending through backend.
        PROBE_TEMPLATE = f'''\
from opensampl.vendors.base_probe import BaseProbe
import pandas as pd
from opensampl.vendors.constants import {self.name}, ProbeKey

class {self.parser_class}(BaseProbe):
    def __init__(self, input_file, **kwargs):
        # TODO: define how to find probe_key (probe_id and ip_address)
        super().__init__(input_file=input_file, **kwargs)

    def process_time_data(self) -> pd.DataFrame:
        """
        Process time series data from the input file.

        Returns:
            pd.DataFrame: DataFrame with columns:
                - time (datetime64[ns]): timestamp for each measurement
                - value (float64): measured value at each timestamp
        """
        # TODO: Implement time series data processing logic specific to {self.name} probes
        raise NotImplementedError("Time data processing not implemented for {self.parser_class}")

    def process_metadata(self) -> dict:
        """
        Process metadata from the input file.

        Returns:
            dict: Dictionary mapping table names to ORM objects
        """
        # TODO: Implement metadata processing logic specific to {self.name}
        raise NotImplementedError("Metadata processing not implemented for {self.parser_class}")
'''  # noqa: N806

        probe_file.write_text(PROBE_TEMPLATE)
        logger.warning(
            f"Wrote {self.parser_class} to {probe_file}. Open the file, and follow TODO instructions to implement."
        )
        return probe_file

    def create_metadata_class(self) -> ast.ClassDef:
        """Create the metadata class AST"""
        class_body = [
            ast.Assign(
                targets=[ast.Name(id="__tablename__", ctx=ast.Store())],
                value=ast.Constant(value=self.metadata_table),
            ),
            ast.Assign(
                targets=[ast.Name(id="probe_uuid", ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id="Column", ctx=ast.Load()),
                    args=[
                        ast.Name(id="String", ctx=ast.Load()),
                        ast.Call(
                            func=ast.Name(id="ForeignKey", ctx=ast.Load()),
                            args=[ast.Constant(value="probe_metadata.uuid")],
                            keywords=[],
                        ),
                    ],
                    keywords=[ast.keyword(arg="primary_key", value=ast.Constant(value=True))],
                ),
            ),
        ]

        # Add fields from config
        for field in self.metadata_fields:
            class_body.append(  # noqa: PERF401
                ast.Assign(
                    targets=[ast.Name(id=field.name, ctx=ast.Store())],
                    value=ast.Call(
                        func=ast.Name(id="Column", ctx=ast.Load()),
                        args=[ast.Name(id=field.sqlalchemy_type, ctx=ast.Load())],
                        keywords=[],
                    ),
                )
            )

        # Add relationship
        class_body.append(
            ast.Assign(
                targets=[ast.Name(id="probe", ctx=ast.Store())],
                value=ast.Call(
                    func=ast.Name(id="relationship", ctx=ast.Load()),
                    args=[ast.Constant(value="ProbeMetadata")],
                    keywords=[
                        ast.keyword(
                            arg="back_populates",
                            value=ast.Constant(value=f"{self.name.lower()}_metadata"),
                        )
                    ],
                ),
            )
        )

        return ast.ClassDef(
            name=self.metadata_orm,
            bases=[ast.Name(id="Base", ctx=ast.Load())],
            keywords=[],
            body=class_body,
            decorator_list=[],
        )

    # def update_constants(self):
    def update_orm_file(self):
        """Update the orm.py file with the new metadata class"""
        orm_path = self.base_path / "db" / "orm.py"

        # Read existing file
        with orm_path.open() as f:
            source = f.read()
            tree = ast.parse(source)

        # Add relationship to ProbeMetadata class
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == "ProbeMetadata":
                # Add relationship field
                node.body.append(
                    ast.Assign(
                        targets=[ast.Name(id=f"{self.name.lower()}_metadata", ctx=ast.Store())],
                        value=ast.Call(
                            func=ast.Name(id="relationship", ctx=ast.Load()),
                            args=[ast.Constant(value=self.metadata_orm)],
                            keywords=[
                                ast.keyword(
                                    arg="back_populates",
                                    value=ast.Constant(value="probe"),
                                ),
                                ast.keyword(arg="uselist", value=ast.Constant(value=False)),
                            ],
                        ),
                    )
                )

        # Create new class and add to tree
        new_class = self.create_metadata_class()
        tree.body.append(new_class)

        module = OrmClassFormatter.format(tree=tree)

        # Write back to file
        with orm_path.open(mode="w") as f:
            f.write(module.code)

    def update_constants(self):
        """Update the constants.py file with the new vendor type"""
        constants_path = self.base_path / "vendors" / "constants.py"

        new_vendor_str = f"""\
{self.name.upper()} = VendorType(
    name='{self.name}',
    parser_class='{self.parser_class}',
    parser_module='{self.parser_module}',
    metadata_table='{self.metadata_table}',
    metadata_orm='{self.metadata_orm}'
)
"""
        new_map_entry = f"\t'{self.name}': {self.name.upper()},"

        file_text = constants_path.read_text()
        tree = ast.parse(file_text)

        for _, node in enumerate(tree.body):
            if (
                isinstance(node, ast.Assign)
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "VENDOR_MAP"
            ):
                vm_lineno = node.lineno
                vm_end_lineno = node.end_lineno
                break
        file_lines = file_text.splitlines()
        if vm_lineno and vm_end_lineno:
            file_lines.insert(vm_end_lineno - 1, new_map_entry)
            file_lines.insert(vm_lineno - 1, new_vendor_str)

        with constants_path.open(mode="w") as f:
            f.write("\n".join(file_lines))

    def create(self):
        """Create the new vendor"""
        self.update_orm_file()
        self.create_probe_file()
        self.update_constants()
