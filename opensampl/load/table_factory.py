"""Database table factory for handling CRUD operations with conflict resolution."""

from typing import Any, Literal, Optional, Union

from loguru import logger
from sqlalchemy import UniqueConstraint, and_, inspect, select
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import BinaryExpression, BooleanClauseList

from opensampl.db.orm import Base

conflict_actions = Literal["error", "replace", "update", "ignore"]


class TableFactory:
    """Factory class for handling database table operations with conflict resolution."""

    def __init__(self, name: str, session: Session):
        """
        Initialize Table Factory Object for db table matching given name.

        Args:
            name: Name of the database table.
            session: SQLAlchemy database session.

        """
        self.name = name
        self.session = session
        self.model = self.resolve_table()
        self.inspector = inspect(self.model)
        self.pk_columns = [col.key for col in self.inspector.primary_key]
        identifiable_const, unique_constraints = self.extract_unique_constraints()
        self.identifiable_constraint = identifiable_const
        self.unique_constraints = unique_constraints

    def resolve_table(self):
        """
        Retrieve the SQLAlchemy model class for the given table name.

        Returns:
            The corresponding SQLAlchemy model class.

        Raises:
            ValueError: If table name is not found in metadata.

        """
        for mapper in Base.registry.mappers:
            if mapper.class_.__tablename__ == self.name:
                return mapper.class_
        raise ValueError(f"Table {self.name} not found in database schema")

    def extract_unique_constraints(self):
        """
        Identify unique constraints that can be used to match existing entries.

        Returns:
            Tuple containing identifiable constraint and list of unique constraints.

        """
        id_const = self.model.identifiable_constraint()
        identifiable_constraint = []
        unique_constraints = []
        for constraint in self.inspector.tables[0].constraints:
            if isinstance(constraint, UniqueConstraint):
                cols = [col.key for col in constraint.columns]
                if id_const and str(constraint.name) == str(id_const):
                    identifiable_constraint = cols
                else:
                    unique_constraints.append(cols)
        return identifiable_constraint, unique_constraints

    def create_col_filter(self, data: dict[str, Any], cols: list[str]):
        """
        Create a SQLAlchemy filter expression for the given columns and data.

        Args:
            data: Dictionary containing the data values.
            cols: List of column names to create filter for.

        Returns:
            SQLAlchemy filter expression or None if columns are missing.

        """
        if cols != [] and all(col in data for col in cols):
            col_data_map = {col: data[col] for col in cols}
            logger.debug(f"column filter= {col_data_map}")
            return and_(*(getattr(self.model, k) == v for k, v in col_data_map.items()))  # ty: ignore[missing-argument]
        logger.debug(f"some or all columns from {cols} missing in data")
        return None

    def print_filter_debug(self, filter_expr: Optional[Union[BinaryExpression, BooleanClauseList]], label: str):
        """
        Print debug information for a filter expression.

        Args:
            filter_expr: The SQLAlchemy filter expression.
            label: Label for the debug output.

        """
        if filter_expr is not None:
            compiled = filter_expr.compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
            logger.debug(f"{label}: {compiled}")

    def find_existing(self, data: dict[str, Any]) -> Optional[Base]:
        """
        Find an existing record that matches the provided data.

        Args:
            data: Dictionary containing the data to match against.

        Returns:
            Existing model instance or None if not found.

        Raises:
            ValueError: If no identifiable fields are provided.

        """
        primary_filter = self.create_col_filter(data=data, cols=self.pk_columns)
        self.print_filter_debug(primary_filter, "Primary filter")
        id_filter = self.create_col_filter(data=data, cols=self.identifiable_constraint)
        self.print_filter_debug(id_filter, "ID Constraint")

        unique_filters = [
            y for y in [self.create_col_filter(data=data, cols=x) for x in self.unique_constraints] if y is not None
        ]
        unique_filter = and_(*unique_filters) if unique_filters != [] else None  # ty: ignore[missing-argument]
        self.print_filter_debug(unique_filter, "Unique Constraint")

        if all(x is None for x in [primary_filter, id_filter, unique_filter]):
            raise ValueError(f"Did not provide identifiable fields for {self.name}")

        if primary_filter is not None:
            existing = self.session.query(self.model).filter(primary_filter).first()  # ty: ignore[missing-argument]
            if existing:
                logger.debug(f"Found {self.name} entry matching primary filters: {existing.to_dict()}")
                return existing

        if id_filter is not None:
            existing = self.session.query(self.model).filter(id_filter).first()  # ty: ignore[missing-argument]
            if existing:
                logger.debug(f"Found {self.name} entry matching identifiable filters: {existing.to_dict()}")
                return existing

        if unique_filter is not None:
            existing = self.session.query(self.model).filter(unique_filter).first()  # ty: ignore[missing-argument]
            if existing:
                logger.debug(f"Found {self.name} entry matching unique filters: {existing.to_dict()}")
                return existing

        return None

    def find_by_field(self, column_name: str, data: Any):
        """
        Get the entries where column = data.

        Args:
            column_name: Name of the column to filter by.
            data: Value to match against.

        Returns:
            List of model instances matching the criteria.

        Raises:
            ValueError: If column name does not exist in the table.

        """
        column = getattr(self.model, column_name, None)
        if column is None:
            raise ValueError(f"Column '{column_name}' does not exist in '{self.name}'.")

        stmt = select(self.model).where(column == data)
        result = self.session.execute(stmt)
        return result.scalars().all()

    def write(self, data: dict[str, Any], if_exists: conflict_actions = "update"):
        """
        Write data to the table that the factory refers to.

        Args:
            data: The data to write to the table.
            if_exists: How to handle conflicts with existing entries. One of:
                - 'update': Only update fields that are provided and non-default (default)
                - 'error': Raise an error if entry exists
                - 'replace': Replace all non-primary-key fields with new values
                - 'ignore': Skip if entry exists

        Returns:
            The created or updated model instance.

        Raises:
            ValueError: If entry exists and if_exists is 'error'.

        """
        existing = self.find_existing(data)

        if not existing:
            new_entry = self.model(**data)
            self.session.add(new_entry)
            logger.debug(f"New entry created in {self.name}")
            self.session.flush()
            return new_entry

        if if_exists == "error":
            logger.error(f"Existing entry: {existing.to_dict()} \nProvided data: {data}")
            raise ValueError(f"Data matched existing entry in {self.name}")

        if if_exists == "ignore":
            logger.debug("Existing entry found, ignoring data")
            return existing

        new_entry = self.model(**data)
        new_entry.resolve_references(session=self.session)

        for col in self.inspector.columns.values():
            if col.key in self.pk_columns:
                continue
            current_value = getattr(existing, col.key)
            new_value = getattr(new_entry, col.key)
            if if_exists == "replace" and (col.key in data or new_value is not None):
                logger.debug(f"Replacing {col.key}: {current_value} -> {new_value}")
                setattr(existing, col.key, new_value)

            elif if_exists == "update" and current_value is None and new_value is not None:
                logger.debug(f"Updating {col.key} from None to {new_value}")
                setattr(existing, col.key, new_value)

        self.session.flush()
        return existing
