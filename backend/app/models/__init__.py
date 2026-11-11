"""Import ORM models here so Alembic can discover their metadata."""

from app.models.base import Base

__all__ = ["Base"]

