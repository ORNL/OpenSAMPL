from contextlib import contextmanager
from typing import Dict, Type
import os
import inspect

from sqlalchemy import (
    create_engine,
    MetaData,
    Table,
    Column,
    ForeignKey,
    Integer,
    LargeBinary,
    text,
    event,
    JSON
)
from sqlalchemy.orm import relationship, declarative_base, sessionmaker, Session
from sqlalchemy.orm.mapper import Mapper
from sqlalchemy.pool import StaticPool
from sqlalchemy.event import listens_for

from opensampl.db.orm import BaseHelpers
from opensampl.metrics import METRICS, MetricType
from opensampl.references import REF_TYPES, ReferenceType

class MockDB:
    def __init__(self, Base=None):
        if Base is None:
            from opensampl.db.orm import Base as PgBase
            Base = PgBase

        self.PgBase = Base
        self.sqlite_metadata = MetaData()
        self.SqliteBase = declarative_base(metadata=self.sqlite_metadata, cls=BaseHelpers)
        path = ":memory:"
        self.engine = create_engine(
            f'sqlite:///{path}',
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=False,
        )
        self.Session = sessionmaker(bind=self.engine)

        # Load SpatiaLite extensions and setup spatial tables
        self._load_spatialite()

        self.table_mappings: Dict[str, Type] = {}
        self.model_overrides: Dict[Type, Type] = {}
        self._create_schema()
        # self._populate_relationships()


    @staticmethod
    def _clone_column(column: Column) -> Column:
        foreign_keys = [
            ForeignKey(
                f"{fk.column.table.name}.{fk.column.name}",
                onupdate=fk.onupdate,
                ondelete=fk.ondelete,
            )
            for fk in column.foreign_keys
        ]

        autoinc = False
        if (
            hasattr(column, "identity")
            and column.identity is not None
            and column.primary_key
        ):
            if isinstance(column.type, Integer) or "int" in str(column.type).lower():
                autoinc = True

        server_default = column.server_default
        if server_default and hasattr(server_default, 'arg'):
            arg_str = str(server_default.arg).lower()

            if "now()" in arg_str:
                server_default = text("CURRENT_TIMESTAMP")
            elif "current_user" in arg_str:
                # SQLite doesn't support this – replace with None
                server_default = None

        if str(column.type) == "BIGINT" or str(column.type) == "BigInteger":
            column_type = Integer()
        elif str(column.type) == "JSONB":
            column_type = JSON()
        else:
            column_type = column.type

        default = column.default
        if column.name == "applied_by":
            default = os.getenv("USER", "ephemeral")

        return Column(
            column.name,
            column_type,
            *foreign_keys,
            primary_key=column.primary_key,
            nullable=column.nullable,
            default=default,
            server_default=server_default,
            unique=column.unique,
            index=column.index,
            autoincrement=autoinc,
            comment=column.comment,
        )

    def _create_schema(self):
        for cls in self.PgBase.__subclasses__():
            table_args = getattr(cls, "__table_args__", ())
            if isinstance(table_args, tuple):
                filtered_args = []
                for arg in table_args:
                    if isinstance(arg, dict) and "schema" in arg:
                        arg_copy = arg.copy()
                        arg_copy.pop("schema", None)
                        if arg_copy:  # Only add if not empty
                            filtered_args.append(arg_copy)
                    else:
                        filtered_args.append(arg)
                table_args = tuple(filtered_args)

            attrs = {
                "__tablename__": cls.__tablename__,
                "__table_args__": table_args,
                "__doc__": cls.__doc__,
            }
            for name, col in cls.__table__.columns.items():
                if not name.startswith("_"):
                    attrs[name] = self._clone_column(col)

            funcs = self._copy_custom_methods(cls, None)
            attrs.update(funcs)
            # Create the MockDB class
            sqlite_cls = type(cls.__name__, (self.SqliteBase, ), attrs)
            # self._copy_custom_methods(cls, sqlite_cls)
            self.table_mappings[cls.__name__] = sqlite_cls
            self.table_mappings[cls.__tablename__] = sqlite_cls
            self.model_overrides[cls] = sqlite_cls
            
            # Register any geometry columns for this table
            self._register_table_geometry_columns(cls, attrs)

        self.sqlite_metadata.create_all(self.engine)

        # Copy SQLAlchemy event listeners after all classes are created
        self._copy_event_listeners()
        
        # Load default metric and reference types after everything is set up
        self._load_default_data()


    def _load_spatialite(self):
        """Load SpatiaLite extension and initialize spatial metadata."""
        try:
            with self.engine.connect() as conn:
                raw_conn = conn.connection.dbapi_connection
                raw_conn.enable_load_extension(True)
                
                # Try to load SpatiaLite extension
                try:
                    raw_conn.load_extension("mod_spatialite")
                except:
                    raw_conn.load_extension("libspatialite")
                
                # Initialize spatial metadata (creates geometry_columns table)
                conn.execute(text("SELECT InitSpatialMetaData(1)"))
                
                # Create geometry columns table if it doesn't exist
                # (InitSpatialMetaData should create this, but let's be explicit)
                conn.execute(text("""
                    CREATE TABLE IF NOT EXISTS geometry_columns (
                        f_table_name TEXT NOT NULL,
                        f_geometry_column TEXT NOT NULL,
                        geometry_type INTEGER NOT NULL,
                        coord_dimension INTEGER NOT NULL,
                        srid INTEGER NOT NULL,
                        spatial_index_enabled INTEGER NOT NULL DEFAULT 0,
                        PRIMARY KEY (f_table_name, f_geometry_column)
                    )
                """))
                
                # Register geometry columns for your tables
                self._register_geometry_columns(conn)
                
                conn.commit()
                print("SpatiaLite loaded successfully with spatial metadata")
                
        except Exception as e:
            print(f"Warning: Could not load SpatiaLite: {e}")
            print("Continuing without spatial support")

    def _register_geometry_columns(self, conn):
        """Register geometry columns in SpatiaLite's geometry_columns table."""
        # This method is now deprecated - geometry columns are registered
        # automatically during schema creation in _register_table_geometry_columns
        pass
    
    def _register_table_geometry_columns(self, original_cls, attrs):
        """Register geometry columns for a specific table as it's being created."""
        try:
            # Check if this table has any geometry columns
            table_name = original_cls.__tablename__
            geometry_columns = []
            
            # Look through the original PostgreSQL columns for geometry types
            for col_name, column in original_cls.__table__.columns.items():
                if hasattr(column.type, 'geometry_type'):
                    # This is a GeoAlchemy2 geometry column
                    geometry_type = self._get_geometry_type_code(column.type.geometry_type)
                    srid = getattr(column.type, 'srid', 4326)
                    geometry_columns.append({
                        'column_name': col_name,
                        'geometry_type': geometry_type,
                        'srid': srid
                    })
            
            # Register each geometry column
            if geometry_columns:
                with self.engine.connect() as conn:
                    for geom_col in geometry_columns:
                        conn.execute(text("""
                            INSERT OR IGNORE INTO geometry_columns 
                            (f_table_name, f_geometry_column, geometry_type, coord_dimension, srid, spatial_index_enabled)
                            VALUES (:table_name, :column_name, :geometry_type, 2, :srid, 0)
                        """), {
                            'table_name': table_name,
                            'column_name': geom_col['column_name'],
                            'geometry_type': geom_col['geometry_type'],
                            'srid': geom_col['srid']
                        })
                    conn.commit()
                    print(f"Registered {len(geometry_columns)} geometry column(s) for table '{table_name}'")
                    
        except Exception as e:
            print(f"Warning: Could not register geometry columns for table '{table_name}': {e}")
    
    def _get_geometry_type_code(self, geometry_type_name):
        """Convert geometry type name to SpatiaLite geometry type code."""
        geometry_types = {
            'POINT': 1,
            'LINESTRING': 2,
            'POLYGON': 3,
            'MULTIPOINT': 4,
            'MULTILINESTRING': 5,
            'MULTIPOLYGON': 6,
            'GEOMETRYCOLLECTION': 7
        }
        return geometry_types.get(geometry_type_name.upper(), 1)  # Default to POINT

    def _copy_custom_methods(self, original_cls, mock_class):
        """Copy custom methods from the original class to the MockDB class.
        
        This handles the class hierarchy differences properly, especially for __init__ methods.
        """
        functions = {}
        # Copy class methods that don't need special handling
        for attr_name in ["identifiable_constraint"]:
            if hasattr(original_cls, attr_name):
                attr_value = getattr(original_cls, attr_name)
                if callable(attr_value):
                    # setattr(mock_class, attr_name, attr_value)
                    functions[attr_name] = attr_value
        
        # Handle __init__ method specially to work with MockDB class hierarchy
        if original_cls.__name__ == 'Locations':
            from geoalchemy2 import WKTElement
            mock_db = self
            def mock_init(self, **kwargs):
                # Handle lat/lon conversion first
                if "lat" in kwargs and "lon" in kwargs:
                    lat = kwargs.pop("lat")
                    lon = kwargs.pop("lon")
                    z = kwargs.pop("z", None)
                    projection = int(kwargs.pop("projection", 4326))
                    point_str = f"POINT({lon} {lat} {z})" if z is not None else f"POINT({lon} {lat})"
                    kwargs["geom"] = WKTElement(point_str, srid=projection)
                
                # Call the parent class constructor properly
                mock_db.SqliteBase.__init__(self, **kwargs)

            # setattr(mock_class, '__init__', mock_init)
            functions['__init__'] = mock_init

        # Handle resolve_references method specially for ProbeMetadata
        elif original_cls.__name__ == 'ProbeMetadata':
            # Get the original resolve_references method
            mockdb_instance = self

            # Create a patched version that uses MockDB table mappings and session
            def mock_resolve_references(self, session: Session = None):
                if not session:
                    try:
                        session = mockdb_instance._get_current_session(self)
                    except RuntimeError:
                        return

                if hasattr(self, "_location_name"):
                    location = session.query(mockdb_instance.table_mappings.get('Locations')).filter_by(name=self._location_name).first()
                    self.location_uuid = location.uuid if location else None
                    delattr(self, "_location_name")  # Clean up after resolving

                if hasattr(self, "_test_name"):
                    test_meta = session.query(mockdb_instance.table_mappings.get('TestMetadata')).filter_by(name=self._test_name).first()
                    self.test_uuid = test_meta.uuid if test_meta else None
                    delattr(self, "_test_name")

            # setattr(mock_class, 'resolve_references', mock_resolve_references)
            functions['resolve_references'] = mock_resolve_references


            def mock_init(self, **kwargs):
                # Handle location_name and test_name conversion
                location_name = kwargs.pop("location_name", None)
                test_name = kwargs.pop("test_name", None)
                
                # Call the parent class constructor properly
                mockdb_instance.SqliteBase.__init__(self, **kwargs)

                # Store name references for later resolution
                if location_name:
                    self._location_name = location_name  # Store it temporarily until we have a session
                if test_name:
                    self._test_name = test_name

            # setattr(mock_class, '__init__', mock_init)
            functions['__init__'] = mock_init

        return functions


    def _copy_event_listeners(self):
        """Copy SQLAlchemy event listeners from original ORM classes to MockDB classes."""
        # Register event listeners for MockDB classes
        self._register_probe_metadata_listener()
        self._register_probe_data_listener()

    def _register_probe_metadata_listener(self):
        """Register resolve_uuid event listener for MockDB ProbeMetadata class."""
        mock_probe_metadata = self.table_mappings.get('ProbeMetadata')
        if mock_probe_metadata:
            @listens_for(mock_probe_metadata, "before_insert")
            def mock_resolve_uuid(mapper, connection, target):
                # Get session from the MockDB Session class
                session = self._get_current_session(target)
                if session:
                    target.resolve_references(session)

    def _register_probe_data_listener(self):
        """Register set_probe_data_defaults event listener for MockDB ProbeData class."""
        mock_probe_data = self.table_mappings.get('ProbeData')
        if mock_probe_data:
            @listens_for(mock_probe_data, "before_insert")
            def mock_set_probe_data_defaults(mapper, connection, target):
                try:
                    session = self._get_current_session(target)
                    
                    if session is None:
                        raise RuntimeError("No session could be resolved from target")

                    # Set default reference_uuid if not provided
                    if target.reference_uuid is None:
                        # Use the actual default reference UUID if available
                        default_ref_uuid = getattr(self, '_default_reference_uuid', "00000000-0000-0000-0000-000000000001")
                        target.reference_uuid = default_ref_uuid

                    # Set default metric_type_uuid if not provided  
                    if target.metric_type_uuid is None:
                        # Use the actual default metric UUID if available
                        default_metric_uuid = getattr(self, '_default_metric_uuid', "00000000-0000-0000-0000-000000000002")
                        target.metric_type_uuid = default_metric_uuid

                except Exception as e:
                    from loguru import logger
                    logger.warning(f"Failed to set default values for ProbeData: {e}")
                    # Continue without setting defaults rather than failing the insert

    def _get_current_session(self, target):
        """Get the current session for a target object, fallback to MockDB session if needed."""
        try:
            # First try the standard SQLAlchemy approach
            session = Session.object_session(target)
            if session:
                return session
        except:
            pass
        
        # Fallback: if we have a current MockDB session, use that
        # This would need to be set by the test framework
        if hasattr(self, '_current_session') and self._current_session:
            return self._current_session
            
        # Last resort: create a new session
        return self.Session()

    def set_current_session(self, session):
        """Set the current session for use by event listeners."""
        self._current_session = session

    def _load_default_data(self):
        """Load default metric types and reference types into the database."""
        session = self.Session()
        try:
            # Load reference types first, then references, then metric types
            default_ref_type_uuid = self._load_reference_types(session)
            default_ref_uuid = self._load_default_reference(session, default_ref_type_uuid)
            default_metric_uuid = self._load_metric_types(session)
            
            # Store the default UUIDs for the event listener
            self._default_reference_uuid = default_ref_uuid
            self._default_metric_uuid = default_metric_uuid
            
            # Load defaults table entries
            self._load_defaults_table(session, default_ref_uuid, default_metric_uuid)
            
            session.commit()
            print("Loaded default metric and reference types from constants")
        except Exception as e:
            session.rollback()
            print(f"Warning: Could not load default data: {e}")
            import traceback
            traceback.print_exc()
        finally:
            session.close()

    def _load_metric_types(self, session):
        """Load metric types from opensampl.metrics.METRICS and return the UNKNOWN one's UUID."""
        MetricTypeTable = self.table_mappings.get('MetricType')
        if not MetricTypeTable:
            return None

        # Get all metric types from the METRICS class
        metrics = [attr for attr in METRICS.__dict__.values() if isinstance(attr, MetricType)]
        phaseerr_uuid = None
        for metric in metrics:
            metric = MetricTypeTable(**metric.model_dump())
            session.add(metric)
            session.flush()
            if metric.name == "PHASE":
                phaseerr_uuid = metric.uuid
        return phaseerr_uuid

    def _load_reference_types(self, session):
        """Load reference types from opensampl.references.REF_TYPES and return the UNKNOWN one's UUID."""
        ReferenceTypeTable = self.table_mappings.get('ReferenceType')
        if not ReferenceTypeTable:
            return None

        referencetypes = [x for x in REF_TYPES.__dict__.values() if isinstance(x, ReferenceType)]
        unknown_ref_type_uuid = None
        for ref in referencetypes:
            ref = ReferenceTypeTable(**ref.model_dump())
            session.add(ref)
            session.flush()
            if ref.name == "UNKNOWN":
                unknown_ref_type_uuid = ref.uuid

        return unknown_ref_type_uuid

    def _load_default_reference(self, session, unknown_ref_type_uuid):
        """Load a default reference entry using the UNKNOWN reference type."""
        ReferenceTable = self.table_mappings.get('Reference')
        if not ReferenceTable or not unknown_ref_type_uuid:
            return None

        default_ref = ReferenceTable(
            reference_type_uuid=unknown_ref_type_uuid,
            compound_reference_uuid=None
        )
        session.add(default_ref)
        session.flush()
        return default_ref.uuid

    def _load_defaults_table(self, session, default_ref_uuid, default_metric_uuid):
        """Load entries into the defaults table for default UUIDs."""
        Defaults = self.table_mappings.get('Defaults')
        if not Defaults:
            return

        default_entries = [
            {
                'table_name': 'reference',
                'uuid': default_ref_uuid
            },
            {
                'table_name': 'metric_type',
                'uuid': default_metric_uuid
            }
        ]

        for default_data in default_entries:
            if default_data['uuid']:  # Only add if we have a valid UUID
                # Check if default entry already exists
                existing = session.query(Defaults).filter_by(table_name=default_data['table_name']).first()
                if not existing:
                    default_entry = Defaults(**default_data)
                    session.add(default_entry)


if __name__ == '__main__':
    db = MockDB()
    with db.Session() as session:
        session.execute(text('SELECT 1;'))