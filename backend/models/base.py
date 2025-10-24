"""
Shared SQLAlchemy Base class for all models.

This module defines the declarative base used by all table models,
preventing circular import issues when models need to be imported
before database configuration.
"""

from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()
