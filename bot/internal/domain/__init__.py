"""
Database models and base configuration
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base for all ORM models (mypy-typed equivalent of declarative_base())."""

# Import all models to ensure they are registered with Base
from .models import *
from .models_realtime import *
