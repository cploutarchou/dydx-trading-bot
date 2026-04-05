"""
Database models and base configuration
"""

from sqlalchemy.orm import declarative_base

Base = declarative_base()

# Import all models to ensure they are registered with Base
from .models import *
from .models_realtime import *
