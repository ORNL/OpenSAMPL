"""Tests for the access ORM module."""

import pytest
from pathlib import Path
from datetime import datetime
from opensampl.db.access_orm import APIAccessKey, Views, Users, Roles, UserRole, add_user_role

def test_access_orm_import():
    """Test that the access ORM module can be imported."""
    from opensampl.db import access_orm
    assert access_orm is not None

def test_api_access_key(db_session):
    """Test APIAccessKey model."""
    key = APIAccessKey(
        key="test-api-key",
        name="Test Key",
        description="Test API Key",
        created_at=datetime.now(),
        expires_at=datetime.now()
    )
    db_session.add(key)
    db_session.commit()
    
    saved_key = db_session.query(APIAccessKey).filter_by(key="test-api-key").first()
    assert saved_key is not None
    assert saved_key.name == "Test Key"
    assert saved_key.description == "Test API Key"

def test_views(db_session):
    """Test Views model."""
    view = Views(
        name="test_view",
        description="Test View",
        query="SELECT * FROM test_table",
        created_at=datetime.now()
    )
    db_session.add(view)
    db_session.commit()
    
    saved_view = db_session.query(Views).filter_by(name="test_view").first()
    assert saved_view is not None
    assert saved_view.description == "Test View"
    assert saved_view.query == "SELECT * FROM test_table"

def test_users(db_session):
    """Test Users model."""
    user = Users(
        username="testuser",
        email="test@example.com",
        password_hash="hashed_password",
        is_active=True,
        created_at=datetime.now(),
        last_login=datetime.now()
    )
    db_session.add(user)
    db_session.commit()
    
    saved_user = db_session.query(Users).filter_by(username="testuser").first()
    assert saved_user is not None
    assert saved_user.email == "test@example.com"
    assert saved_user.is_active is True

def test_roles(db_session):
    """Test Roles model."""
    role = Roles(
        name="test_role",
        description="Test Role",
        permissions=["read", "write"],
        created_at=datetime.now()
    )
    db_session.add(role)
    db_session.commit()
    
    saved_role = db_session.query(Roles).filter_by(name="test_role").first()
    assert saved_role is not None
    assert saved_role.description == "Test Role"
    assert saved_role.permissions == ["read", "write"]

def test_user_role(db_session):
    """Test UserRole model and add_user_role function."""
    # Create test user and role
    user = Users(
        username="testuser",
        email="test@example.com",
        password_hash="hashed_password",
        is_active=True,
        created_at=datetime.now()
    )
    role = Roles(
        name="test_role",
        description="Test Role",
        permissions=["read"],
        created_at=datetime.now()
    )
    db_session.add_all([user, role])
    db_session.commit()
    
    # Test add_user_role function
    add_user_role(db_session, user.id, role.id)
    
    # Verify the association
    user_role = db_session.query(UserRole).filter_by(
        user_id=user.id,
        role_id=role.id
    ).first()
    assert user_role is not None

def test_user_role_unique_constraint(db_session):
    """Test unique constraint on UserRole."""
    # Create test user and role
    user = Users(
        username="testuser",
        email="test@example.com",
        password_hash="hashed_password",
        is_active=True,
        created_at=datetime.now()
    )
    role = Roles(
        name="test_role",
        description="Test Role",
        permissions=["read"],
        created_at=datetime.now()
    )
    db_session.add_all([user, role])
    db_session.commit()
    
    # Add role to user
    add_user_role(db_session, user.id, role.id)
    
    # Try to add the same role again
    with pytest.raises(Exception):  # Should raise unique constraint violation
        add_user_role(db_session, user.id, role.id)

def test_api_key_expiration(db_session):
    """Test API key expiration."""
    expired_key = APIAccessKey(
        key="expired-key",
        name="Expired Key",
        description="Expired API Key",
        created_at=datetime.now(),
        expires_at=datetime.now()  # Already expired
    )
    db_session.add(expired_key)
    db_session.commit()
    
    saved_key = db_session.query(APIAccessKey).filter_by(key="expired-key").first()
    assert saved_key is not None
    assert saved_key.is_expired() is True

def test_view_query_validation(db_session):
    """Test view query validation."""
    with pytest.raises(ValueError):
        Views(
            name="invalid_view",
            description="Invalid View",
            query="INVALID SQL QUERY",
            created_at=datetime.now()
        )

def test_user_password_validation(db_session):
    """Test user password validation."""
    with pytest.raises(ValueError):
        Users(
            username="testuser",
            email="test@example.com",
            password_hash="",  # Empty password
            is_active=True,
            created_at=datetime.now()
        )

def test_role_permissions_validation(db_session):
    """Test role permissions validation."""
    with pytest.raises(ValueError):
        Roles(
            name="test_role",
            description="Test Role",
            permissions=[],  # Empty permissions
            created_at=datetime.now()
        ) 