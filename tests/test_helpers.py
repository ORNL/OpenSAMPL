"""Tests for the helpers module package structure."""

import pkgutil
from pathlib import Path


def test_helpers_package_import():
    """Test that the helpers package can be imported."""
    import opensampl.helpers

    assert opensampl.helpers is not None


def test_helpers_submodules():
    """Test that all helpers submodules can be imported."""
    import opensampl.helpers

    submodules = [name for _, name, _ in pkgutil.iter_modules(opensampl.helpers.__path__)]
    assert "env" in submodules
    assert "source_writer" in submodules
    assert "create_vendor" in submodules


def test_helpers_module_files():
    """Test that required helpers module files exist."""
    helpers_dir = Path(opensampl.helpers.__file__).parent
    required_files = ["__init__.py", "env.py", "source_writer.py", "create_vendor.py"]
    for file in required_files:
        assert (helpers_dir / file).exists(), f"Required file {file} not found in helpers module"


def test_env_module_import():
    """Test that the env module can be imported."""
    from opensampl.helpers import env

    assert env is not None


def test_source_writer_module_import():
    """Test that the source_writer module can be imported."""
    from opensampl.helpers import source_writer

    assert source_writer is not None


def test_create_vendor_module_import():
    """Test that the create_vendor module can be imported."""
    from opensampl.helpers import create_vendor

    assert create_vendor is not None
