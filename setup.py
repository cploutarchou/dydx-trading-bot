"""
Setup configuration for dYdX Trading Bot Backend package.
"""

from setuptools import find_packages, setup

setup(
    name="dydx-trading-bot-backend",
    version="1.0.0",
    description="FastAPI backend for dYdX Trading Bot backtest management",
    author="Cristos Ploutarchou",
    author_email="cploutarchou@gmail.com",
    packages=find_packages(where="."),
    python_requires=">=3.12",
    install_requires=[
        "fastapi==0.104.1",
        "uvicorn[standard]==0.24.0",
        "sqlalchemy==2.0.23",
        "alembic==1.13.0",
        "pydantic==2.5.0",
        "pydantic-settings==2.1.0",
        "pydantic[email]==2.5.0",
        "python-jose[cryptography]==3.3.0",
        "passlib[bcrypt]==1.7.4",
        "bcrypt==4.1.1",
        "python-multipart==0.0.6",
        "psycopg2-binary==2.9.9",
        "python-dotenv==1.0.0",
    ],
    entry_points={
        "console_scripts": [
            "dydx-backend=backend.main:main",
        ],
    },
)
