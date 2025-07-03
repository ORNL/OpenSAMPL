"""Data Factory for defining the unique probe/metric/reference combination to use for Data readings"""

from typing import Any, Optional

from loguru import logger
from sqlalchemy.inspection import inspect
from sqlalchemy.orm import Session

from opensampl.db.orm import Base
from opensampl.db.orm import MetricType as DBMetricType
from opensampl.db.orm import ProbeMetadata as DBProbe
from opensampl.db.orm import Reference as DBReference
from opensampl.db.orm import ReferenceType as DBReferenceType
from opensampl.load.table_factory import TableFactory
from opensampl.metrics import METRICS, MetricType
from opensampl.references import REF_TYPES, CompoundReferenceType, ReferenceType
from opensampl.vendors.constants import ProbeKey


class DataFactory:
    """
    Data factory for defining the unique probe/metric/reference combination for Data readings

    Will take the references and attempt to resolve them into a probe, metric type, and reference object. The reference
    object will also have the database object for any compound references filled as well.
    """

    probe: Optional[DBProbe] = None
    metric: Optional[DBMetricType] = None
    db_ref_type: Optional[DBReferenceType] = None
    reference: Optional[DBReference] = None
    db_compound_reference: Optional[Base] = None

    def __init__(
        self,
        probe_key: ProbeKey,
        metric_type: MetricType,
        reference_type: ReferenceType,
        session: Session,
        compound_key: Optional[dict[str, Any]] = None,
        strict: bool = True,
    ):
        """
        Initialize the Data Factory for defining the unique probe/metric/reference combination for Data readings.

        Args:
            probe_key: The probe key identifying the probe.
            metric_type: The type of metric being tracked.
            reference_type: The type of reference for the data.
            session: Database session for operations.
            compound_key: Optional dictionary for compound reference lookups.
            strict: If True, raises errors for missing objects. If False, logs warnings.

        """
        self.probe_key = probe_key
        self.metric_type = metric_type
        self.reference_type = reference_type
        self.compound_key = compound_key
        self.session = session
        self.strict = strict
        self.fill_db_values()

    def dump_factory(self):
        """
        Dump a dict version of the data factory

        Returns:
            dictionary with all the relevant fields for a data factory

        """
        return {
            "db_probe": self.probe.to_dict() if self.probe else None,
            "db_metric": self.metric.to_dict() if self.metric else None,
            "db_ref_type": self.db_ref_type.to_dict() if self.db_ref_type else None,
            "db_reference": self.reference.to_dict() if self.reference else None,
            "db_compound_reference": self.db_compound_reference.to_dict() if self.db_compound_reference else None,
            "probe_key": self.probe_key.model_dump(),
            "metric_type": self.metric_type.model_dump_json(),
            "reference_type": self.reference_type.model_dump(),
            "compound_key": self.compound_key,
        }

    def fill_db_values(self):
        """
        Fill in the probe, metric, reference, and compound reference from the database.

        Returns:
            Self for method chaining.

        """
        self.get_probe()  # find the probe object

        self.get_metric_type()  # find the metric type object
        self.session.flush()

        self.get_reference_type()  # find the reference type
        self.session.flush()

        self.get_compound_reference()  # find what is being referenced, if applicable
        self.session.flush()

        self.get_reference()  # put the reference type and what is being referenced together to get the Reference
        self.session.flush()

        return self

    def not_found(self, msg: str, unstrict_msg: str = "Filling value with UNKNOWN") -> None:
        """
        Handle cases where object is not found. Behavior varies based on the strict mode of the data factory.

        Args:
            msg: The message that is either logged (strict=False) or thrown as an error (strict=True).
            unstrict_msg: An additional portion of logging message for alternate behavior when strict=False.

        """
        if self.strict:
            raise ValueError(msg)
        logger.warning(f"{msg}. {unstrict_msg}")

    def get_probe(self):
        """
        Get the probe object for the data.

        Raises:
            ValueError: If probe with the given key is not found.

        """
        probe_factory = TableFactory("probe_metadata", session=self.session)
        self.probe = probe_factory.find_existing(data=self.probe_key.model_dump())

        if not self.probe:
            raise ValueError(f"Probe with key {self.probe_key} not found")

    def get_metric_type(self):
        """
        Get the metric type object for the data.

        If the metric type doesn't exist, attempts to create it. If creation fails,
        falls back to UNKNOWN metric type.
        """
        metric_factory = TableFactory("metric_type", session=self.session)
        self.metric = metric_factory.find_existing(data=self.metric_type.model_dump())

        if self.metric is not None:
            return

        try:
            self.metric = metric_factory.write(self.metric_type.model_dump(), if_exists="ignore")
        except Exception as e:
            logger.error(e)
            self.not_found(f"No Metric type matching {self.metric_type} found, and could not create it.")
        else:
            return

        self.metric = metric_factory.find_existing(data=METRICS.UNKNOWN.model_dump())
        self.metric_type = METRICS.UNKNOWN

        return

    def get_reference_type(self):
        """
        Get the reference type object for the data.

        Handles both simple and compound reference types. For compound types,
        attempts to find existing types or creates unknown compound types.
        """
        ref_type_factory = TableFactory("reference_type", session=self.session)
        self.db_ref_type = ref_type_factory.find_existing(data=self.reference_type.model_dump())

        if self.db_ref_type is not None:
            return

        if not isinstance(self.reference_type, CompoundReferenceType):
            self.not_found(f"No Reference type matching {self.reference_type} found")
            self.db_ref_type = ref_type_factory.find_existing(data=REF_TYPES.UNKNOWN.model_dump())
            self.reference_type = REF_TYPES.UNKNOWN
            return

        # Now we deal with the CompoundReferenceTypes, who reference another table

        self.not_found(
            f"No Reference type matching {self.reference_type} found",
            unstrict_msg=f"Attempting to find existing type for the {self.reference_type.reference_table}",
        )

        options = ref_type_factory.find_by_field(
            column_name="reference_table", data=self.reference_type.reference_table
        )
        if len(options) == 0:
            logger.warning(
                f"No existing reference type found: Auto generating Reference Type "
                f"against {self.reference_type.reference_table}"
            )
            unknown_compound = CompoundReferenceType(
                name=f"UNKNOWN - {self.reference_type.reference_table}",
                description=f"Autogenerated reference type for table {self.reference_type.reference_table}",
                reference_table=self.reference_type.reference_table,
            )
            self.reference_type = unknown_compound
            self.db_ref_type = ref_type_factory.write(data=unknown_compound.model_dump(), if_exists="ignore")
            return

        logger.warning(
            f"Existing reference type to table {self.reference_type.reference_table} found, "
            f"attempting to find one intended for unknown type..."
        )

        unknown_opts = [x for x in options if "unknown" in x.name.lower()]
        if len(unknown_opts) > 0:
            self.db_ref_type = unknown_opts[0]
            if len(unknown_opts) > 1:
                logger.warning(f'Multiple options with "unknown" in name, using first result: {self.db_ref_type}')

            self.reference_type = CompoundReferenceType(
                name=self.db_ref_type.name,
                description=self.db_ref_type.description,
                reference_table=self.db_ref_type.reference_table,
            )
            return

        logger.warning("No UNKNOWN reference type options found, creating one")
        unknown_compound = CompoundReferenceType(
            name=f"UNKNOWN - {self.reference_type.reference_table}",
            description=f"Autogenerated reference type for table {self.reference_type.reference_table}",
            reference_table=self.reference_type.reference_table,
        )
        self.reference_type = unknown_compound
        self.db_ref_type = ref_type_factory.write(data=unknown_compound.model_dump(), if_exists="ignore")

        return

    def get_compound_reference(self):
        """
        Retrieve the object used as a compound reference in the data's reference type.

        Only applies to compound reference types. Uses the compound_key to find
        the referenced object in the appropriate table.
        """
        if not isinstance(self.reference_type, CompoundReferenceType):
            return

        if self.compound_key is None:
            self.not_found(
                (
                    f"Reference type {self.reference_type.name} is compound, yet no reference "
                    f"to {self.reference_type.reference_table} was given in compound_key field"
                ),
                unstrict_msg="Leaving as None, may cause unexpected behavior in interface",
            )
            return

        lookup_factory = TableFactory(self.reference_type.reference_table, session=self.session)
        self.db_compound_reference = lookup_factory.find_existing(data=self.compound_key)

        if self.db_compound_reference is not None:
            return

        self.not_found(
            f"Could not find {self.reference_type.reference_table} entry matching {self.compound_key}",
            unstrict_msg="Filling with None, may cause unexpected behavior in interface",
        )

    def get_reference(self):
        """
        Get the reference object for the data.

        Creates a reference linking the reference type and compound reference.

        Raises:
            ValueError: If compound reference has multiple or no primary keys.

        """
        reference_factory = TableFactory("reference", session=self.session)
        reference_data = {"reference_type_uuid": self.db_ref_type.uuid, "compound_reference_uuid": None}

        if self.db_compound_reference is not None:
            primary_values = inspect(self.db_compound_reference).identity
            if len(primary_values) > 1:
                raise ValueError(
                    f"Referenced Entity Object for {self.reference_type} Reference type has multiple primary keys: "
                    f"{self.db_compound_reference.to_dict()}"
                )
            if len(primary_values) == 0:
                raise ValueError(
                    f"Referenced Entity Object for {self.reference_type} Reference type Has no primary key: "
                    f"{self.db_compound_reference.to_dict()}"
                )

            reference_data["compound_reference_uuid"] = primary_values[0]
        logger.debug(f"{reference_data=}")
        # Write with if_exists='ignore' will return a found existing object matching the fields.
        self.reference = reference_factory.write(data=reference_data, if_exists="ignore")
