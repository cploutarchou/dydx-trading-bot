"""
Pytest configuration and fixtures for backend tests.

Provides database session, authentication, and test utilities.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database import Base, get_db
from backend.main import app

# Test database URL (in-memory SQLite for fast tests)
TEST_DATABASE_URL = "sqlite:///:memory:"


@pytest.fixture(scope="function")
def db_engine():
    """Create test database engine."""
    engine = create_engine(
        TEST_DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    # Ensure all tables are created before tests run
    Base.metadata.create_all(bind=engine)
    yield engine
    # Cleanup after tests
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def db_session(db_engine):
    """Create test database session."""
    TestingSessionLocal = sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine
    )
    session = TestingSessionLocal()
    yield session
    session.close()


@pytest.fixture(scope="function")
def client(db_session):
    """FastAPI test client with database session override."""
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield TestClient(app)
    # Cleanup dependency overrides
    app.dependency_overrides.clear()


@pytest.fixture(scope="session")
def anyio_backend():
    """Use asyncio for async tests."""
    return "asyncio"
