"""Pytest configuration and fixtures."""

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from opensampl.db.orm import Base, SCHEMA_NAME

@pytest.fixture(scope="function")
def db_session():
    """Create a new database session for a test."""
    # Create engine with SQLite
    engine = create_engine("sqlite:///:memory:")
    
    # Create tables
    Base.metadata.create_all(engine)
    
    # Create session
    Session = sessionmaker(bind=engine)
    session = Session()
    
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)

# Configure pytest to ignore certain modules
collect_ignore = ["orm.py"] 