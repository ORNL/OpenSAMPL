"""Tests for the access ORM module."""

from datetime import datetime

import pytest

from opensampl.db.access_orm import APIAccessKey, Roles, Users, Views


def test_access_orm_import():
    """Test that the access ORM module can be imported."""
    from opensampl.db import access_orm

    assert access_orm is not None


def test_api_access_key(db_session):
    """Test APIAccessKey model."""
    # Skip if using SQLite (PostGIS functions not available)
    if "sqlite" in str(db_session.bind.url):
        pytest.skip("PostGIS functions not available in SQLite")
        
    key = APIAccessKey(
        key="test-api-key",
        created_at=datetime.now(),
        expires_at=datetime.now(),
    )
    db_session.add(key)
    db_session.commit()

    saved_key = db_session.query(APIAccessKey).filter_by(key="test-api-key").first()
    assert saved_key is not None
    assert saved_key.key == "test-api-key"


def test_views(db_session):
    """Test Views model."""
    # Skip if using SQLite (PostGIS functions not available)
    if "sqlite" in str(db_session.bind.url):
        pytest.skip("PostGIS functions not available in SQLite")
        
    view = Views(name="test_view")
    db_session.add(view)
    db_session.commit()

    saved_view = db_session.query(Views).filter_by(name="test_view").first()
    assert saved_view is not None
    assert saved_view.name == "test_view"


def test_users(db_session):
    """Test Users model."""
    # Skip if using SQLite (PostGIS functions not available)
    if "sqlite" in str(db_session.bind.url):
        pytest.skip("PostGIS functions not available in SQLite")
        
    user = Users(
        email="test@example.com",
    )
    db_session.add(user)
    db_session.commit()

    saved_user = db_session.query(Users).filter_by(email="test@example.com").first()
    assert saved_user is not None
    assert saved_user.email == "test@example.com"


def test_roles(db_session):
    """Test Roles model."""
    # Skip if using SQLite (PostGIS functions not available)
    if "sqlite" in str(db_session.bind.url):
        pytest.skip("PostGIS functions not available in SQLite")
        
    role = Roles(name="test_role")
    db_session.add(role)
    db_session.commit()

    saved_role = db_session.query(Roles).filter_by(name="test_role").first()
    assert saved_role is not None
    assert saved_role.name == "test_role"


def test_api_key_expiration(db_session):
    """Test API key expiration."""
    # Skip if using SQLite (PostGIS functions not available)
    if "sqlite" in str(db_session.bind.url):
        pytest.skip("PostGIS functions not available in SQLite")
        
    expired_key = APIAccessKey(
        key="expired-key",
        created_at=datetime.now(),
        expires_at=datetime.now(),  # Already expired
    )
    db_session.add(expired_key)
    db_session.commit()

    saved_key = db_session.query(APIAccessKey).filter_by(key="expired-key").first()
    assert saved_key is not None
    assert saved_key.is_expired() is True
