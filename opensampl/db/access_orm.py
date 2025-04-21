"""ORM for managing access to openSAMPL database and endpoints"""
import secrets
import uuid
from datetime import datetime
from typing import List, Union

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.orm.exc import NoResultFound
from sqlalchemy.schema import MetaData

Base = declarative_base(metadata=MetaData(schema="access"))


class APIAccessKey(Base):
    """Table for recording and managing API access keys."""

    __tablename__ = "api_access_keys"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(64), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)

    def generate_key(self):
        """Generate the API access key."""
        self.key = secrets.token_urlsafe(48)
        return self.key

    def is_expired(self):
        """Check if API access key is expired."""
        return self.expires_at is not None and datetime.utcnow() > self.expires_at


class Views(Base):
    """Table for recording and managing views."""

    __tablename__ = "views"
    view_id = Column(Text, primary_key=True, default=str(uuid.uuid4()))
    name = Column(Text)

    @staticmethod
    def get_view_by_name(session, name):
        """Get view by name"""
        try:
            return session.query(Views).filter_by(name=name).one()
        except NoResultFound:
            print(f"View with name {name} not found")
            return None


class Roles(Base):
    """Table for recording and managing roles."""

    __tablename__ = "roles"
    role_id = Column(Text, primary_key=True, default=str(uuid.uuid4()))
    name = Column(Text)
    view_id = Column(Text, ForeignKey("views.view_id"))

    @staticmethod
    def get_role_by_name(session, name):
        """Get role by name"""
        try:
            return session.query(Roles).filter_by(name=name).one()
        except NoResultFound:
            print(f"Role with name {name} not found")
            return None


class Users(Base):
    """Table for recording and managing users."""

    __tablename__ = "users"
    user_id = Column(Text, primary_key=True, default=str(uuid.uuid4()))
    email = Column(Text)

    @staticmethod
    def get_user_by_email(session, email):
        """Get user by email"""
        try:
            return session.query(Users).filter_by(email=email).one()
        except NoResultFound:
            print(f"User with email {email} not found")
            return None


class UserRole(Base):
    """Table for recording and managing user roles."""

    __tablename__ = "user_role"
    user_id = Column(Text, ForeignKey("users.user_id"), primary_key=True)
    role_id = Column(Text, ForeignKey("roles.role_id"), primary_key=True)


def add_user_role(emails: Union[str, List[str]], role_name: str, session):
    """Add user role to the database."""
    if isinstance(emails, str):
        emails = [emails]

    role = Roles.get_role_by_name(name=role_name)
    if role is None:
        print(f"Role with name {role_name} not found")
        return

    for email in emails:
        user = Users.get_user_by_email(email=email)
        if user is None:
            # Create a new user if not found
            user = Users(email=email)
            session.add(user)
            session.flush()  # Flush to get the generated user_id
            print(f"New user created with email {email}")

        # Check if user already has the specified role
        if any(ur.role_id == role.role_id for ur in user.user_role):
            print(f"User with email {email} already has role {role_name}")
            continue

        # Create a new entry in user_role table
        user_role = UserRole(user_id=user.user_id, role_id=role.role_id)
        session.add(user_role)
        print(f"User with email {email} assigned role {role_name}")
        session.commit()


Views.roles = relationship("Roles")
Roles.user_role = relationship("UserRole")
Users.user_role = relationship("UserRole")
