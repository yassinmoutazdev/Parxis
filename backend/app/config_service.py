"""Configuration Service for runtime-adjustable parameters.

Corresponds to PRD Epic 10.2 - Configuration & Settings.
Corresponds to ARCHITECTURE Section 12.2 (Runtime-Adjustable Config).
"""

import logging
from typing import Any

from app.db.engine import Session
from app.db.models.system import Config

logger = logging.getLogger(__name__)

# Default values - correspond to scheduler/mastery.py constants
DEFAULT_DECAY_RATE = 0.0077  # ~50% after 90 days
DEFAULT_CORRECT_THRESHOLD = 0.7
DEFAULT_EASE_FACTOR_INCREMENT = 0.1
DEFAULT_EASE_FACTOR_MAX = 3.0
DEFAULT_EASE_FACTOR_DECREMENT = 0.2
DEFAULT_EASE_FACTOR_MIN = 1.3
DEFAULT_MASTERY_BONUS = 0.15
DEFAULT_MASTERY_PENALTY = 0.25
DEFAULT_CATEGORY_BALANCE = 0.6

# Proficiency blend weights for quiz retrieval
DEFAULT_PROFICIENCY_BLEND_WEIGHTS = {
    "weakness": 0.4,
    "random": 0.3,
    "recency": 0.3,
}

# Backup retention defaults (from Settings)
DEFAULT_BACKUP_RETENTION_DAILY = 14
DEFAULT_BACKUP_RETENTION_MONTHLY = 6


# Configuration key definitions with validation
CONFIG_DEFINITIONS: dict[str, dict[str, Any]] = {
    "decay_rate": {
        "type": "float",
        "min": 0.0,
        "max": 1.0,
        "default": DEFAULT_DECAY_RATE,
        "description": "Mastery decay rate (higher = faster decay)",
    },
    "correct_threshold": {
        "type": "float",
        "min": 0.0,
        "max": 1.0,
        "default": DEFAULT_CORRECT_THRESHOLD,
        "description": "Minimum score to count as correct",
    },
    "ease_factor_increment": {
        "type": "float",
        "min": 0.0,
        "max": 1.0,
        "default": DEFAULT_EASE_FACTOR_INCREMENT,
        "description": "Ease factor increment on correct answer",
    },
    "ease_factor_max": {
        "type": "float",
        "min": 1.0,
        "max": 5.0,
        "default": DEFAULT_EASE_FACTOR_MAX,
        "description": "Maximum ease factor",
    },
    "ease_factor_decrement": {
        "type": "float",
        "min": 0.0,
        "max": 1.0,
        "default": DEFAULT_EASE_FACTOR_DECREMENT,
        "description": "Ease factor decrement on incorrect answer",
    },
    "ease_factor_min": {
        "type": "float",
        "min": 0.5,
        "max": 2.0,
        "default": DEFAULT_EASE_FACTOR_MIN,
        "description": "Minimum ease factor",
    },
    "mastery_bonus": {
        "type": "float",
        "min": 0.0,
        "max": 1.0,
        "default": DEFAULT_MASTERY_BONUS,
        "description": "Mastery increase on correct answer",
    },
    "mastery_penalty": {
        "type": "float",
        "min": 0.0,
        "max": 1.0,
        "default": DEFAULT_MASTERY_PENALTY,
        "description": "Mastery decrease on incorrect answer",
    },
    "category_balance_ratio": {
        "type": "float",
        "min": 0.0,
        "max": 1.0,
        "default": DEFAULT_CATEGORY_BALANCE,
        "description": "Target proportion of items from categories with due items",
    },
    "proficiency_blend_weights": {
        "type": "json",
        "default": DEFAULT_PROFICIENCY_BLEND_WEIGHTS,
        "description": "Blend weights for quiz retrieval (weakness, random, recency)",
    },
    "backup_retention_daily": {
        "type": "int",
        "min": 1,
        "max": 365,
        "default": DEFAULT_BACKUP_RETENTION_DAILY,
        "description": "Number of daily backups to retain",
    },
    "backup_retention_monthly": {
        "type": "int",
        "min": 1,
        "max": 24,
        "default": DEFAULT_BACKUP_RETENTION_MONTHLY,
        "description": "Number of monthly backups to retain",
    },
    "vault_path": {
        "type": "string",
        # Genuinely unset until the learner picks one in Settings -- do NOT
        # fall back to app_settings.vault_path here, or the UI can never
        # tell "nothing saved yet" apart from "this happens to be the
        # default folder name."
        "default": "",
        "description": "Path to the Obsidian vault Praxis watches for notes (not set until chosen in Settings)",
    },
    "ollama_api_key": {
        "type": "string",
        # Always "" until a key is validated and saved via Connect. Note:
        # str(app_settings.ollama_api_key) would previously default to the
        # literal string "None" when unset (since ollama_api_key is None),
        # which is truthy -- silently reporting the key as "configured"
        # with no real key present.
        "default": "",
        "description": "Ollama Cloud API key (required -- Praxis is Ollama Cloud-only)",
    },
}


class ConfigServiceError(Exception):
    """Base exception for config service errors."""

    pass


class ConfigValidationError(ConfigServiceError):
    """Raised when config validation fails."""

    pass


class ConfigService:
    """Service for managing runtime-adjustable configuration parameters.

    Loads configuration from the Config table, falling back to defaults
    defined in CONFIG_DEFINITIONS when not set.
    """

    _cache: dict[str, Any] | None = None

    @classmethod
    def _load_all(cls) -> dict[str, Any]:
        """Load all config values from database, falling back to defaults."""
        if cls._cache is not None:
            return cls._cache

        cls._cache = {}

        # Initialize with defaults
        for key, definition in CONFIG_DEFINITIONS.items():
            cls._cache[key] = definition["default"]

        # Override with database values
        try:
            with Session() as session:
                configs = session.query(Config).all()
                for config in configs:
                    if config.key in CONFIG_DEFINITIONS:
                        definition = CONFIG_DEFINITIONS[config.key]
                        value = cls._parse_value(config.value, definition["type"])
                        cls._cache[config.key] = value
        except Exception as e:
            logger.warning(f"Failed to load config from database: {e}")

        return cls._cache

    @classmethod
    def _parse_value(cls, value: str, value_type: str) -> Any:
        """Parse a string value to its typed representation."""
        if value_type == "float":
            return float(value)
        elif value_type == "int":
            return int(value)
        elif value_type == "bool":
            return value.lower() in ("true", "1", "yes")
        elif value_type == "json":
            import json

            return json.loads(value)
        elif value_type == "string":
            return value
        return value

    @classmethod
    def _validate_value(cls, key: str, value: Any) -> None:
        """Validate a config value against its definition."""
        if key not in CONFIG_DEFINITIONS:
            raise ConfigValidationError(f"Unknown config key: {key}")

        definition = CONFIG_DEFINITIONS[key]
        value_type = definition["type"]

        if value_type == "float":
            if not isinstance(value, (int, float)):
                raise ConfigValidationError(f"{key} must be a number")
            if "min" in definition and value < definition["min"]:
                raise ConfigValidationError(
                    f"{key} must be >= {definition['min']}"
                )
            if "max" in definition and value > definition["max"]:
                raise ConfigValidationError(f"{key} must be <= {definition['max']}")
        elif value_type == "int":
            if not isinstance(value, int):
                raise ConfigValidationError(f"{key} must be an integer")
            if "min" in definition and value < definition["min"]:
                raise ConfigValidationError(
                    f"{key} must be >= {definition['min']}"
                )
            if "max" in definition and value > definition["max"]:
                raise ConfigValidationError(f"{key} must be <= {definition['max']}")
        elif value_type == "json":
            if not isinstance(value, dict):
                raise ConfigValidationError(f"{key} must be a JSON object")
        elif value_type == "string":
            if not isinstance(value, str):
                raise ConfigValidationError(f"{key} must be a string")

    @classmethod
    def get(cls, key: str) -> Any:
        """Get a config value by key.

        Args:
            key: The config key to retrieve

        Returns:
            The config value (typed according to definition)

        Raises:
            ConfigServiceError: If the key is unknown
        """
        if key not in CONFIG_DEFINITIONS:
            raise ConfigServiceError(f"Unknown config key: {key}")

        cls._load_all()
        return cls._cache.get(key, CONFIG_DEFINITIONS[key]["default"])

    @classmethod
    def get_all(cls) -> dict[str, Any]:
        """Get all config values with their definitions.

        Returns:
            Dict with config keys and their current values plus metadata
        """
        cls._load_all()

        result = {}
        for key, definition in CONFIG_DEFINITIONS.items():
            result[key] = {
                "value": cls._cache.get(key, definition["default"]),
                "type": definition["type"],
                "min": definition.get("min"),
                "max": definition.get("max"),
                "default": definition["default"],
                "description": definition["description"],
            }

        return result

    @classmethod
    def set(cls, key: str, value: Any) -> dict[str, Any]:
        """Set a config value.

        Args:
            key: The config key to set
            value: The value to set (typed according to definition)

        Returns:
            Dict with the updated config value

        Raises:
            ConfigValidationError: If the value is invalid
            ConfigServiceError: If the key is unknown
        """
        # Validate
        cls._validate_value(key, value)

        # Serialize to string based on type
        definition = CONFIG_DEFINITIONS[key]
        if definition["type"] == "json":
            import json

            value_str = json.dumps(value)
        elif definition["type"] == "bool":
            value_str = "true" if value else "false"
        else:
            value_str = str(value)

        # Upsert in database
        with Session() as session:
            existing = session.query(Config).filter(Config.key == key).first()
            if existing:
                existing.value = value_str
            else:
                config = Config(key=key, value=value_str)
                session.add(config)
            session.commit()

        # Update cache
        if cls._cache is not None:
            cls._cache[key] = value

        logger.info(f"Config updated: {key} = {value}")

        return {"key": key, "value": value}

    @classmethod
    def reset_cache(cls) -> None:
        """Reset the config cache (useful after external changes)."""
        cls._cache = None


def get_scheduler_settings() -> dict[str, Any]:
    """Get scheduler-specific settings (convenience function).

    Returns:
        Dict with decay_rate, correct_threshold, and mastery values
    """
    return {
        "decay_rate": ConfigService.get("decay_rate"),
        "correct_threshold": ConfigService.get("correct_threshold"),
        "ease_factor_increment": ConfigService.get("ease_factor_increment"),
        "ease_factor_max": ConfigService.get("ease_factor_max"),
        "ease_factor_decrement": ConfigService.get("ease_factor_decrement"),
        "ease_factor_min": ConfigService.get("ease_factor_min"),
        "mastery_bonus": ConfigService.get("mastery_bonus"),
        "mastery_penalty": ConfigService.get("mastery_penalty"),
    }


def get_retrieval_settings() -> dict[str, Any]:
    """Get retrieval-specific settings (convenience function).

    Returns:
        Dict with category_balance_ratio and proficiency_blend_weights
    """
    return {
        "category_balance_ratio": ConfigService.get("category_balance_ratio"),
        "proficiency_blend_weights": ConfigService.get("proficiency_blend_weights"),
    }


def get_backup_settings() -> dict[str, Any]:
    """Get backup-specific settings (convenience function).

    Returns:
        Dict with backup_retention_daily and backup_retention_monthly
    """
    return {
        "backup_retention_daily": ConfigService.get("backup_retention_daily"),
        "backup_retention_monthly": ConfigService.get("backup_retention_monthly"),
    }
