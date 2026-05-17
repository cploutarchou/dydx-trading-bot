"""
Database initialization script.

Creates authentication tables. Bootstrap admin creation is opt-in through
environment variables so local setup does not inject hardcoded credentials.
"""

from datetime import datetime
import os
from typing import Optional, Type, Union

from loguru import logger
from sqlalchemy.orm import Session

from src.api.auth_utils import PasswordUtils
from src.infrastructure.database import db, init_db
from src.infrastructure.domain.models.auth_models import User


def create_admin_user(session: Session) -> Optional[Union[Type[User], User]]:
    """
    Create a bootstrap admin user only when BOOTSTRAP_ADMIN_PASSWORD is set.
    """
    # Check if the admin user already exists
    existing_admin = session.query(User).filter(User.username == "admin").first()

    if existing_admin:
        logger.info("Admin user already exists")
        return existing_admin

    bootstrap_password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "").strip()
    if not bootstrap_password:
        logger.warning(
            "Skipping bootstrap admin creation because BOOTSTRAP_ADMIN_PASSWORD is not set"
        )
        return None

    bootstrap_email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "admin@localhost").strip()
    bootstrap_username = os.getenv("BOOTSTRAP_ADMIN_USERNAME", "admin").strip() or "admin"

    # Create admin user
    admin_user = User(
        username=bootstrap_username,
        email=bootstrap_email or "admin@localhost",
        hashed_password=PasswordUtils.hash_password(
            bootstrap_password[:72]
        ),  # Truncate to 72 bytes for bcrypt
        first_name="System",
        last_name="Administrator",
        is_active=True,
        is_superuser=True,
        is_2fa_enabled=False,
        created_at=datetime.utcnow(),
        password_changed_at=datetime.utcnow(),
    )

    session.add(admin_user)
    session.commit()
    session.refresh(admin_user)

    logger.info("✅ Bootstrap admin user created:")
    logger.info(f"   Username: {bootstrap_username}")
    logger.info(f"   Email: {bootstrap_email or 'admin@localhost'}")
    logger.info("⚠️  IMPORTANT: Change the default password after first login!")

    return admin_user


def test_email_config():
    """
    Test email configuration
    """
    try:
        from decouple import config

        email_provider = config("EMAIL_PROVIDER", default="")

        if str(email_provider).lower() == "mailgun":
            api_key = config("MAILGUN_API_KEY", default="")
            domain = config("MAILGUN_DOMAIN", default="")

            if api_key and domain:
                logger.info("✅ Mailgun configuration found")
            else:
                logger.warning(
                    "⚠️  Mailgun configuration incomplete (API_KEY or DOMAIN missing)"
                )

        elif str(email_provider).lower() == "smtp":
            smtp_host = config("SMTP_HOST", default="")
            smtp_username = config("SMTP_USERNAME", default="")

            if smtp_host and smtp_username:
                logger.info("✅ SMTP configuration found")
            else:
                logger.warning("⚠️  SMTP configuration incomplete")
        else:
            logger.warning(
                "⚠️  No email provider configured. Set EMAIL_PROVIDER in .env"
            )

    except Exception as e:
        logger.warning(f"⚠️  Email configuration test failed: {e}")


def initialize_auth_database():
    """
    Initialize authentication database tables and optional bootstrap admin user.
    """
    try:
        logger.info("🚀 Starting database initialization...")

        # Initialize database tables
        logger.info("📦 Creating database tables...")
        init_db()
        logger.info("✅ Database tables created successfully")

        # Create bootstrap admin user when explicitly configured.
        logger.info("👤 Checking bootstrap admin configuration...")
        session = db.get_session()
        try:
            admin_user = create_admin_user(session)
            if admin_user is not None:
                logger.info(f"✅ Admin user ready with ID: {getattr(admin_user, 'id')}")
        finally:
            session.close()

        # Test database connection
        logger.info("🔍 Testing database connection...")
        if db.health_check():
            logger.info("✅ Database health check passed")
        else:
            logger.error("❌ Database health check failed")
            return False

        # Test email configuration (optional)
        logger.info("📧 Testing email configuration...")
        test_email_config()

        logger.info("🎉 Database initialization completed successfully!")
        return True

    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        return False


def main():
    """
    Main initialization function
    """
    print("=" * 60)
    print("dYdX Trading Bot - Authentication Database Setup")
    print("=" * 60)

    # Initialize main database
    success = initialize_auth_database()

    if success:
        print("\n" + "=" * 60)
        print("🎉 SETUP COMPLETE!")
        print("=" * 60)
        print("Bootstrap Admin User:")
        print("  Set BOOTSTRAP_ADMIN_PASSWORD before running this script to create one.")
        print()
        print("API Endpoints:")
        print("  Login: POST /auth/login")
        print("  2FA Email Verification: POST /auth/2fa/request-email-verification")
        print("  Email Test (Admin): POST /auth/test-email")
        print("  Swagger UI: http://localhost:8889/docs")
        print()
        print("📧 Email Configuration:")
        print(
            "  1. Edit config/profiles/<environment>.config.enc.json with make dev-config"
        )
        print("  2. Configure MAILGUN_API_KEY and MAILGUN_DOMAIN")
        print("  3. Or set up SMTP with your email provider")
        print("  4. Test with: POST /auth/test-email")
        print()
        print("⚠️  Security Notes:")
        print("  1. Use a unique bootstrap admin password and rotate it after first login")
        print("  2. Enable 2FA with email verification for all production users")
        print("  3. Update SECRET_KEY in production environment")
        print("  4. Configure email provider for 2FA and password reset")
        print("=" * 60)

    else:
        print("\n" + "=" * 60)
        print("❌ SETUP FAILED!")
        print("=" * 60)
        print("Check the logs above for error details.")
        print("=" * 60)
        exit(1)


if __name__ == "__main__":
    main()
