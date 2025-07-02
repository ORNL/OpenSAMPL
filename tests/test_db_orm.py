"""Tests for the database ORM module package structure."""

import pkgutil
from pathlib import Path

import opensampl.db


def test_db_package_import():
    """Test that the db package can be imported."""
    import opensampl.db

    assert opensampl.db is not None


def test_db_submodules():
    """Test that all db submodules can be imported."""
    import opensampl.db

    submodules = [name for _, name, _ in pkgutil.iter_modules(opensampl.db.__path__)]
    assert "orm" in submodules


def test_db_module_files():
    """Test that required db module files exist."""
    db_dir = Path(opensampl.db.__file__).parent
    required_files = ["__init__.py", "orm.py"]
    for file in required_files:
        assert (db_dir / file).exists(), f"Required file {file} not found in db module"


def test_orm_module_import():
    """Test that the orm module can be imported."""
    from opensampl.db import orm

    assert orm is not None


def test_orm_base_class():
    """Test that the Base class exists."""
    from opensampl.db.orm import Base

    assert Base is not None


def test_orm_model_classes():
    """Test that all required model classes exist."""
    from opensampl.db.orm import AdvaMetadata, Locations, ProbeData, ProbeMetadata, TestMetadata

    assert Locations is not None
    assert TestMetadata is not None
    assert ProbeMetadata is not None
    assert ProbeData is not None
    assert AdvaMetadata is not None
