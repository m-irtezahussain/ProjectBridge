from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all tenant-scoped ORM models."""

