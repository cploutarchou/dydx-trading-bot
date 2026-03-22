"""
Database initialization script
Creates authentication tables and default admin user
"""

import logging
from datetime import datetime
from typing import Type, Union

from auth_utils import PasswordUtils
from database import db, init_db
from internal.domain.models.auth_models import User
from sqlalchemy.orm import Session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_admin_user(session: Session) -> Union[Type[User], User]:
    """
    Create default admin user if it doesn't exist
    Username: admin
    Password: admin123
    """
    # Check if the admin user already exists
    existing_admin = session.query(User).filter(User.username == "admin").first()

    if existing_admin:
        logger.info("Admin user already exists")
        return existing_admin

    # Create admin user
    admin_user = User(
        username="admin",
        email="admin@localhost",
        hashed_password=PasswordUtils.hash_password(
            "admin123"[:72]
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

    logger.info("✅ Default admin user created:")
    logger.info("   Username: admin")
    logger.info("   Password: admin123")
    logger.info("   Email: admin@localhost")
    logger.info("⚠️  IMPORTANT: Change the default password after first login!")

    return admin_user


def test_email_config():
    """
    Test email configuration
    """
    try:
        from decouple import config

        email_provider = config("EMAIL_PROVIDER", default="")

        if email_provider.lower() == "mailgun":
            api_key = config("MAILGUN_API_KEY", default="")
            domain = config("MAILGUN_DOMAIN", default="")

            if api_key and domain:
                logger.info("✅ Mailgun configuration found")
            else:
                logger.warning("⚠️  Mailgun configuration incomplete (API_KEY or DOMAIN missing)")

        elif email_provider.lower() == "smtp":
            smtp_host = config("SMTP_HOST", default="")
            smtp_username = config("SMTP_USERNAME", default="")

            if smtp_host and smtp_username:
                logger.info("✅ SMTP configuration found")
            else:
                logger.warning("⚠️  SMTP configuration incomplete")
        else:
            logger.warning("⚠️  No email provider configured. Set EMAIL_PROVIDER in .env")

    except Exception as e:
        logger.warning(f"⚠️  Email configuration test failed: {e}")


def initialize_auth_database():
    """
    Initialize authentication database tables and create the default admin user
    """
    try:
        logger.info("🚀 Starting database initialization...")

        # Initialize database tables
        logger.info("📦 Creating database tables...")
        init_db()
        logger.info("✅ Database tables created successfully")

        # Create admin user
        logger.info("👤 Creating default admin user...")
        session = db.get_session()
        try:
            admin_user = create_admin_user(session)
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


def create_test_users(session: Session):
    """
    Create additional test users for development
    """
    test_users = [
        {
            "username": "user1",
            "email": "user1@localhost",
            "password": "password123",
            "first_name": "Test",
            "last_name": "User1",
            "is_superuser": False,
        },
        {
            "username": "user2",
            "email": "user2@localhost",
            "password": "password123",
            "first_name": "Test",
            "last_name": "User2",
            "is_superuser": False,
        },
    ]

    created_count = 0
    for user_data in test_users:
        existing_user = session.query(User).filter(User.username == user_data["username"]).first()

        if not existing_user:
            test_user = User(
                username=user_data["username"],
                email=user_data["email"],
                hashed_password=PasswordUtils.hash_password(user_data["password"]),
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
                is_active=True,
                is_superuser=user_data["is_superuser"],
                is_2fa_enabled=False,
                created_at=datetime.utcnow(),
                password_changed_at=datetime.utcnow(),
            )

            session.add(test_user)
            created_count += 1

    if created_count > 0:
        session.commit()
        logger.info(f"✅ Created {created_count} test users")
    else:
        logger.info("Test users already exist")


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
        # Create test users in development
        try:
            logger.info("👥 Creating test users...")
            session = db.get_session()
            try:
                create_test_users(session)
            finally:
                session.close()
        except Exception as e:
            logger.warning(f"Test user creation failed (not critical): {e}")

        print("\n" + "=" * 60)
        print("🎉 SETUP COMPLETE!")
        print("=" * 60)
        print("Default Admin User:")
        print("  Username: admin")
        print("  Password: admin123")
        print("  Email: admin@localhost")
        print()
        print("API Endpoints:")
        print("  Login: POST /auth/login")
        print("  2FA Email Verification: POST /auth/2fa/request-email-verification")
        print("  Email Test (Admin): POST /auth/test-email")
        print("  Swagger UI: http://localhost:8000/docs")
        print()
        print("📧 Email Configuration:")
        print("  1. Copy .env.example to .env")
        print("  2. Configure MAILGUN_API_KEY and MAILGUN_DOMAIN")
        print("  3. Or set up SMTP with your email provider")
        print("  4. Test with: POST /auth/test-email")
        print()
        print("⚠️  Security Notes:")
        print("  1. Change admin password immediately after first login")
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
