"""ORM for managing access to openSAMPL database and endpoints"""

import secrets
from datetime import UTC, datetime

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_base
from sqlalchemy.schema import MetaData

Base = declarative_base(metadata=MetaData(schema="access"))


class APIAccessKey(Base):
    """Table for recording and managing API access keys."""

    __tablename__ = "api_access_keys"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(64), unique=True, nullable=False, index=True)
    created_at = Column(DateTime, default=lambda: datetime.now(UTC).replace(tzinfo=None), nullable=False)
    expires_at = Column(DateTime, nullable=True)

    def generate_key(self) -> str:
        """
        Generate the API access key.

        Returns:
            The generated access key string.

        """
        self.key = secrets.token_urlsafe(48)
        return self.key

    def is_expired(self) -> bool:
        """
        Check if API access key is expired.

        Returns:
            True if the key is expired, False otherwise.

        """
        if self.expires_at is None:
            return False
        expiry = self.expires_at
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=UTC)
        return datetime.now(tz=UTC) > expiry
