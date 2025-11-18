"""
FastAPI Application Configuration with JWT Authentication
Configures Swagger UI with Bearer token authentication and includes auth routes
"""

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from midleware.auth_middleware import get_admin_user, get_current_active_user
from internal.domain.models.auth_models import User

# Import authentication modules
from routes.auth import router as auth_router
from routes.password_2fa_routes import router as password_2fa_router


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application with authentication
    """
    # Initialize FastAPI app with custom OpenAPI configuration
    app = FastAPI(
        title="dYdX Trading Bot API",
        description="Authenticated API for managing multiple dYdX trading bot instances",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Configure appropriately for production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include authentication routes
    app.include_router(auth_router)
    app.include_router(password_2fa_router)

    # Custom OpenAPI schema with JWT Bearer authentication
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title="dYdX Trading Bot API",
            version="1.0.0",
            description="Authenticated API for managing multiple dYdX trading bot instances with JWT authentication and 2FA support",
            routes=app.routes,
        )

        # Add JWT Bearer authentication to OpenAPI schema
        openapi_schema["components"]["securitySchemes"] = {
            "BearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Enter your JWT access token obtained from /auth/login",
            }
        }

        # Apply security to all endpoints except auth endpoints
        for path, path_item in openapi_schema["paths"].items():
            # Skip authentication for auth endpoints and health checks
            if path.startswith("/auth/") or path.endswith("/health"):
                continue

            for method, operation in path_item.items():
                if method.lower() in ["get", "post", "put", "delete", "patch"]:
                    operation["security"] = [{"BearerAuth": []}]

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    return app


# Create the main app instance
app = create_app()


# ============================================================================
# PROTECTED API ENDPOINTS (Examples)
# ============================================================================


@app.get("/api/v1/protected/test")
async def protected_test_endpoint(
    current_user: User = Depends(get_current_active_user),
):
    """
    Test endpoint that requires authentication
    """
    return {
        "message": "This is a protected endpoint",
        "user": {
            "username": getattr(current_user, "username"),
            "email": getattr(current_user, "email"),
            "is_superuser": getattr(current_user, "is_superuser", False),
        },
    }


@app.get("/api/v1/admin/test")
async def admin_test_endpoint(current_user: User = Depends(get_admin_user)):
    """
    Test endpoint that requires admin privileges
    """
    return {
        "message": "This is an admin-only endpoint",
        "admin_user": {
            "username": getattr(current_user, "username"),
            "email": getattr(current_user, "email"),
        },
    }


# ============================================================================
# PUBLIC ENDPOINTS
# ============================================================================


@app.get("/")
async def root():
    """
    Root endpoint - public access
    """
    return {
        "message": "dYdX Trading Bot API",
        "version": "1.0.0",
        "status": "running",
        "docs": "/docs",
        "authentication": {
            "login": "/auth/login",
            "register": "/auth/register",
            "docs": "Visit /docs for interactive authentication",
        },
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint - public access
    """
    return {
        "status": "healthy",
        "service": "dydx-trading-bot-api",
        "timestamp": "2024-01-01T00:00:00Z",
    }


if __name__ == "__main__":
    import uvicorn

    # For development
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True, log_level="info")
