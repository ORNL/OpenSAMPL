"""Test that the package can be imported and that a simple test passes."""

import pytest


def test_import():
    """Verify that the package can be imported."""
    try:
        import opensampl

        assert opensampl.__doc__
    except ImportError:
        pytest.fail("Failed to import opensampl package")


def test_always_passes():
    """A simple test that always passes."""
    assert True
