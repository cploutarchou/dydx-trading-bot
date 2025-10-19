"""
REST API endpoint tests for backtest strategy management.

Tests JWT authentication, authorization, error handling,
and full API integration.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.auth import create_access_token
from backend.database import User, get_db
from backend.main import app
from backend.services import BacktestStrategyService, UserService


@pytest.fixture
def client(db_session: Session):
    """FastAPI test client with database session override."""

    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    return TestClient(app)


@pytest.fixture
def test_user_model(db_session: Session) -> User:
    """Create test user via UserService."""
    return UserService.create_user(
        db=db_session,
        username="testuser",
        email="test@example.com",
        password="testpassword123",
    )


@pytest.fixture
def another_user_model(db_session: Session) -> User:
    """Create another test user."""
    return UserService.create_user(
        db=db_session,
        username="anotheruser",
        email="another@example.com",
        password="anotherpassword123",
    )


@pytest.fixture
def test_user_token(test_user_model: User) -> str:
    """Create JWT token for test user."""
    return create_access_token(subject=test_user_model.username)


@pytest.fixture
def another_user_token(another_user_model: User) -> str:
    """Create JWT token for another user."""
    return create_access_token(subject=another_user_model.username)


@pytest.fixture
def auth_headers(test_user_token: str) -> dict:
    """Authorization headers with JWT token."""
    return {"Authorization": f"Bearer {test_user_token}"}


class TestStrategyEndpointsCreate:
    """Test strategy creation endpoints."""

    def test_create_strategy_success(
        self,
        client: TestClient,
        auth_headers: dict,
        db_session: Session,
        test_user_model: User,
    ):
        """Test successful strategy creation."""
        payload = {
            "name": "Test Strategy",
            "description": "A test strategy",
            "category": "custom",
            "zscore_threshold": 1.5,
            "stats_window": 21,
            "max_half_life": 24,
            "usd_per_trade": 100.0,
            "usd_min_collateral": 500.0,
        }

        response = client.post(
            "/api/v1/strategies",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "Test Strategy"
        assert data["data"]["user_id"] == test_user_model.id

    def test_create_strategy_missing_required_fields(
        self, client: TestClient, auth_headers: dict
    ):
        """Test creating strategy with missing required fields."""
        payload = {
            "description": "Missing required fields",
        }

        response = client.post(
            "/api/v1/strategies",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 422  # Unprocessable Entity

    def test_create_strategy_unauthorized(self, client: TestClient):
        """Test creating strategy without authentication."""
        payload = {
            "name": "Unauthorized",
            "description": "No auth",
            "category": "test",
        }

        response = client.post(
            "/api/v1/strategies",
            json=payload,
        )

        assert response.status_code == 403  # Forbidden (no bearer token)


class TestStrategyEndpointsRead:
    """Test strategy retrieval endpoints."""

    def test_get_user_strategies(
        self,
        client: TestClient,
        auth_headers: dict,
        db_session: Session,
        test_user_model: User,
    ):
        """Test retrieving user's strategies."""
        # Create test strategies
        BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user_model.id,
            name="Strategy 1",
            description="First",
            category="test",
        )
        BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user_model.id,
            name="Strategy 2",
            description="Second",
            category="test",
        )

        response = client.get(
            "/api/v1/strategies",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["strategies"]) == 2

    def test_get_strategy_by_id(
        self,
        client: TestClient,
        auth_headers: dict,
        db_session: Session,
        test_user_model: User,
    ):
        """Test retrieving specific strategy."""
        strategy = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user_model.id,
            name="Retrieved Strategy",
            description="To be retrieved",
            category="test",
        )

        response = client.get(
            f"/api/v1/strategies/{strategy.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "Retrieved Strategy"

    def test_get_nonexistent_strategy(self, client: TestClient, auth_headers: dict):
        """Test retrieving non-existent strategy."""
        response = client.get(
            "/api/v1/strategies/99999",
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_get_public_strategies(
        self, client: TestClient, db_session: Session, test_user_model: User
    ):
        """Test retrieving public strategies (no auth required)."""
        BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user_model.id,
            name="Public Strategy",
            description="Public",
            category="test",
            is_public=True,
        )

        response = client.get("/api/v1/strategies/public")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["strategies"]) >= 1


class TestStrategyEndpointsUpdate:
    """Test strategy update endpoints."""

    def test_update_strategy_success(
        self,
        client: TestClient,
        auth_headers: dict,
        db_session: Session,
        test_user_model: User,
    ):
        """Test successful strategy update."""
        strategy = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user_model.id,
            name="Original Name",
            description="Original",
            category="test",
        )

        payload = {
            "name": "Updated Name",
            "zscore_threshold": 2.0,
        }

        response = client.put(
            f"/api/v1/strategies/{strategy.id}",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["name"] == "Updated Name"
        assert data["data"]["zscore_threshold"] == 2.0

    def test_update_nonexistent_strategy(self, client: TestClient, auth_headers: dict):
        """Test updating non-existent strategy."""
        payload = {"name": "New Name"}

        response = client.put(
            "/api/v1/strategies/99999",
            json=payload,
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_update_unauthorized_strategy(
        self,
        client: TestClient,
        auth_headers: dict,
        db_session: Session,
        another_user_model: User,
    ):
        """Test updating another user's strategy."""
        # Create strategy owned by another user
        strategy = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=another_user_model.id,
            name="Other User's Strategy",
            description="Not mine",
            category="test",
        )

        payload = {"name": "Hacked!"}

        response = client.put(
            f"/api/v1/strategies/{strategy.id}",
            json=payload,
            headers=auth_headers,
        )

        # Should fail with 403 Forbidden
        assert response.status_code == 403


class TestStrategyEndpointsDelete:
    """Test strategy deletion endpoints."""

    def test_delete_strategy_success(
        self,
        client: TestClient,
        auth_headers: dict,
        db_session: Session,
        test_user_model: User,
    ):
        """Test successful strategy deletion."""
        strategy = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user_model.id,
            name="To Delete",
            description="Deletable",
            category="test",
        )

        response = client.delete(
            f"/api/v1/strategies/{strategy.id}",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Verify deletion
        deleted = BacktestStrategyService.get_strategy_by_id(
            db=db_session,
            strategy_id=strategy.id,
        )
        assert deleted is None

    def test_delete_nonexistent_strategy(self, client: TestClient, auth_headers: dict):
        """Test deleting non-existent strategy."""
        response = client.delete(
            "/api/v1/strategies/99999",
            headers=auth_headers,
        )

        assert response.status_code == 404

    def test_delete_unauthorized_strategy(
        self,
        client: TestClient,
        auth_headers: dict,
        db_session: Session,
        another_user_model: User,
    ):
        """Test deleting another user's strategy."""
        strategy = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=another_user_model.id,
            name="Other User's Strategy",
            description="Not mine",
            category="test",
        )

        response = client.delete(
            f"/api/v1/strategies/{strategy.id}",
            headers=auth_headers,
        )

        assert response.status_code == 403


class TestStrategyEndpointsDefaults:
    """Test default strategy endpoints."""

    def test_set_default_strategy(
        self,
        client: TestClient,
        auth_headers: dict,
        db_session: Session,
        test_user_model: User,
    ):
        """Test setting default strategy."""
        strategy = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user_model.id,
            name="New Default",
            description="Will be default",
            category="test",
        )

        response = client.post(
            f"/api/v1/strategies/{strategy.id}/set-default",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["is_default"] is True

    def test_get_default_strategy(
        self,
        client: TestClient,
        auth_headers: dict,
        db_session: Session,
        test_user_model: User,
    ):
        """Test retrieving user's default strategy."""
        strategy = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user_model.id,
            name="Default",
            description="Default strategy",
            category="test",
        )

        BacktestStrategyService.set_default_strategy(
            db=db_session,
            user_id=test_user_model.id,
            strategy_id=strategy.id,
        )

        response = client.get(
            "/api/v1/strategies/default",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["is_default"] is True


class TestStrategyEndpointsStats:
    """Test strategy statistics endpoints."""

    def test_get_strategy_stats(
        self,
        client: TestClient,
        auth_headers: dict,
        db_session: Session,
        test_user_model: User,
    ):
        """Test retrieving strategy usage statistics."""
        strategy = BacktestStrategyService.create_strategy(
            db=db_session,
            user_id=test_user_model.id,
            name="Stats Strategy",
            description="For stats",
            category="test",
        )

        response = client.get(
            f"/api/v1/strategies/{strategy.id}/stats",
            headers=auth_headers,
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "total_runs" in data["data"]
        assert "completed_runs" in data["data"]


# Helper import for dependency override
# Note: These type hints are for developer documentation
# Runtime values are properly unwrapped from SQLAlchemy ORM objects
