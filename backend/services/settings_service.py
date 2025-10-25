"""
Settings management service for bot configuration.

Handles getting/setting bot configuration parameters from database.
Supports per-user settings and system-wide defaults.
"""

import json
from datetime import datetime
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from models.settings import BotSetting


class SettingsService:
    """Service for managing bot settings in database."""

    @staticmethod
    def get_settings_schema() -> Dict[str, Any]:
        """Return the schema/definition of all available settings."""
        return {
            "sections": [
                {
                    "section": "logging",
                    "title": "Logging",
                    "description": "Logging configuration",
                    "fields": [
                        {
                            "key": "level",
                            "label": "Log Level",
                            "description": "Logging level (DEBUG, INFO, WARNING, ERROR)",
                            "value_type": "string",
                            "default_value": "INFO",
                            "options": ["DEBUG", "INFO", "WARNING", "ERROR"],
                            "required": True,
                        },
                        {
                            "key": "loki_enabled",
                            "label": "Enable Loki",
                            "description": "Send logs to Loki aggregator",
                            "value_type": "boolean",
                            "default_value": False,
                            "required": False,
                        },
                        {
                            "key": "loki_url",
                            "label": "Loki URL",
                            "description": "Loki server URL (e.g., http://localhost:3100)",
                            "value_type": "string",
                            "default_value": "http://localhost:3100",
                            "required": False,
                        },
                    ],
                },
                {
                    "section": "telegram",
                    "title": "Telegram Notifications",
                    "description": "Configure Telegram bot for alerts",
                    "fields": [
                        {
                            "key": "token",
                            "label": "Bot Token",
                            "description": "Telegram bot token from BotFather",
                            "value_type": "string",
                            "default_value": "",
                            "required": False,
                            "placeholder": "1234567890:ABCDefGHIjklmnOpqrsTUVwxYZ123456789",
                        },
                        {
                            "key": "chat_id",
                            "label": "Chat ID",
                            "description": "Telegram chat ID for alerts",
                            "value_type": "string",
                            "default_value": "",
                            "required": False,
                            "placeholder": "1234567890",
                        },
                    ],
                },
                {
                    "section": "dydx",
                    "title": "dYdX Connection",
                    "description": "dYdX network configuration",
                    "fields": [
                        {
                            "key": "is_testnet",
                            "label": "Use Testnet",
                            "description": "Trade on testnet instead of mainnet",
                            "value_type": "boolean",
                            "default_value": True,
                            "required": False,
                        },
                        {
                            "key": "chain_id",
                            "label": "Chain ID",
                            "description": "dYdX chain ID",
                            "value_type": "string",
                            "default_value": "dydx-mainnet-1",
                            "required": False,
                        },
                    ],
                },
                {
                    "section": "redis",
                    "title": "Redis Cache",
                    "description": "Redis configuration for caching",
                    "fields": [
                        {
                            "key": "enabled",
                            "label": "Enable Redis",
                            "description": "Use Redis for caching",
                            "value_type": "boolean",
                            "default_value": True,
                            "required": False,
                        },
                        {
                            "key": "host",
                            "label": "Host",
                            "description": "Redis host",
                            "value_type": "string",
                            "default_value": "localhost",
                            "required": False,
                        },
                        {
                            "key": "port",
                            "label": "Port",
                            "description": "Redis port",
                            "value_type": "int",
                            "default_value": 6379,
                            "required": False,
                            "min_value": 1,
                            "max_value": 65535,
                        },
                        {
                            "key": "cache_ttl_seconds",
                            "label": "Cache TTL (seconds)",
                            "description": "Time to live for cached data",
                            "value_type": "int",
                            "default_value": 86400,
                            "required": False,
                            "min_value": 60,
                            "max_value": 31536000,
                        },
                    ],
                },
            ]
        }

    @staticmethod
    def get_all_settings(db: Session) -> Dict[str, Any]:
        """Get all current settings grouped by section."""
        schema = SettingsService.get_settings_schema()
        settings = db.query(BotSetting).filter(BotSetting.is_active == True).all()

        # Build a dict of current values
        settings_dict = {}
        for setting in settings:
            key = f"{setting.section}.{setting.key}"
            settings_dict[key] = setting

        # Build response with schema and values
        sections = []
        for section in schema["sections"]:
            section_name = section["section"]
            settings_list = []

            for field in section["fields"]:
                key = f"{section_name}.{field['key']}"
                setting = settings_dict.get(key)

                # Parse value
                if setting:
                    try:
                        value = json.loads(setting.value)
                    except (json.JSONDecodeError, TypeError):
                        value = setting.value
                else:
                    value = field.get("default_value")

                settings_list.append(
                    {
                        "section": section_name,
                        "key": field["key"],
                        "label": field["label"],
                        "description": field["description"],
                        "value_type": field["value_type"],
                        "value": value,
                        "default_value": field.get("default_value"),
                        "required": field.get("required", False),
                        "options": field.get("options"),
                        "min_value": field.get("min_value"),
                        "max_value": field.get("max_value"),
                        "placeholder": field.get("placeholder"),
                    }
                )

            sections.append(
                {
                    "section": section_name,
                    "settings": settings_list,
                }
            )

        return {"sections": sections}

    @staticmethod
    def update_settings(db: Session, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update multiple settings at once.
        
        Args:
            db: Database session
            updates: Dict of "section.key": value pairs
            
        Returns:
            Updated settings
        """
        for setting_key, value in updates.items():
            if "." not in setting_key:
                continue

            section, key = setting_key.split(".", 1)

            # Find or create setting
            setting = (
                db.query(BotSetting)
                .filter(BotSetting.section == section, BotSetting.key == key)
                .first()
            )

            if not setting:
                # Create new setting
                setting = BotSetting(
                    section=section,
                    key=key,
                    value=json.dumps(value),
                    value_type=type(value).__name__,
                    is_active=True,
                )
                db.add(setting)
            else:
                # Update existing setting
                setting.value = json.dumps(value)
                setting.value_type = type(value).__name__
                setting.updated_at = datetime.utcnow()

        db.commit()
        return SettingsService.get_all_settings(db)

    @staticmethod
    def get_setting(db: Session, section: str, key: str) -> Optional[Any]:
        """Get a single setting value."""
        setting = (
            db.query(BotSetting)
            .filter(
                BotSetting.section == section,
                BotSetting.key == key,
                BotSetting.is_active == True,
            )
            .first()
        )

        if not setting:
            return None

        try:
            return json.loads(setting.value)
        except (json.JSONDecodeError, TypeError):
            return setting.value

    @staticmethod
    def set_setting(db: Session, section: str, key: str, value: Any) -> None:
        """Set a single setting."""
        setting = (
            db.query(BotSetting)
            .filter(BotSetting.section == section, BotSetting.key == key)
            .first()
        )

        if not setting:
            setting = BotSetting(
                section=section,
                key=key,
                value=json.dumps(value),
                value_type=type(value).__name__,
                is_active=True,
            )
            db.add(setting)
        else:
            setting.value = json.dumps(value)
            setting.value_type = type(value).__name__
            setting.updated_at = datetime.utcnow()

        db.commit()

    @staticmethod
    def initialize_defaults(db: Session) -> None:
        """Initialize default settings if they don't exist."""
        schema = SettingsService.get_settings_schema()

        for section in schema["sections"]:
            for field in section["fields"]:
                setting = (
                    db.query(BotSetting)
                    .filter(
                        BotSetting.section == section["section"],
                        BotSetting.key == field["key"],
                    )
                    .first()
                )

                if not setting:
                    setting = BotSetting(
                        section=section["section"],
                        key=field["key"],
                        value=json.dumps(field.get("default_value")),
                        value_type=field.get("value_type", "string"),
                        default_value=json.dumps(field.get("default_value")),
                        description=field.get("description", ""),
                        is_active=True,
                    )
                    db.add(setting)

        db.commit()
