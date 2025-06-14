import json
import logging
from pathlib import Path
from typing import Any

from . import app_config  # Still needed for APP_NAME (for logger) and defaults
from .exceptions import ConfigError

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")

NUM_EQ_BANDS = 10  # Number of equalizer bands


class ConfigManager:
    """Manages application settings and custom EQ curves persistence."""

    def __init__(self, config_dir_path: Path) -> None:
        """Initializes the ConfigManager.

        Args:
            config_dir_path: The OS-specific path to the application's config directory.
        """
        self._config_dir = config_dir_path
        self._settings_file_path = self._config_dir / "settings.json"
        self._custom_eq_curves_file_path = self._config_dir / "custom_eq_curves.json"

        # Ensure the configuration directory exists
        try:
            self._config_dir.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            logger.exception("Could not create config directory %s", self._config_dir)
            # Depending on desired behavior, could raise an exception here or try to proceed
            # For now, log error and continue; loading will likely fail gracefully.

        self._settings: dict[str, Any] = self._load_json_file(self._settings_file_path)
        self._custom_eq_curves: dict[str, list[int]] = self._load_json_file(
            self._custom_eq_curves_file_path,
        )

        if not self._custom_eq_curves:  # Initialize with defaults if empty or load failed
            self._custom_eq_curves = app_config.DEFAULT_EQ_CURVES.copy()
            # Attempt to save only if directory creation was successful or not attempted
            if self._config_dir.exists():
                self._save_json_file(
                    self._custom_eq_curves_file_path,
                    self._custom_eq_curves,
                )
            else:
                logger.warning("Config directory does not exist. Skipping initial save of default EQ curves.")

    def _load_json_file(self, file_path: Path) -> dict:
        if file_path.exists():
            try:
                with file_path.open("r", encoding="utf-8") as f:  # Specify encoding
                    return json.load(f)
            except json.JSONDecodeError:
                logger.exception(
                    "Failed to decode JSON from file %s. Using empty config for this file.",
                    file_path,
                )
                return {}
            except OSError as e:
                logger.exception("OSError while reading file %s. Using empty config for this file.", file_path)
                return {}
        else:
            logger.info("Config file %s not found. Returning empty dict.", file_path)
        return {}

    def _save_json_file(self, file_path: Path, data: dict) -> None:
        if not self._config_dir.exists():
            logger.error("Cannot save file %s because config directory %s does not exist.", file_path, self._config_dir)
            return
        try:
            with file_path.open("w", encoding="utf-8") as f:  # Specify encoding
                json.dump(data, f, indent=4)
        except OSError:
            logger.exception("Error saving JSON file %s", file_path)

    # General Settings
    def get_setting(self, key: str, default: Any = None) -> Any:
        """Retrieves a setting value by key."""
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        """Sets a setting value by key and saves all settings."""
        self._settings[key] = value
        self._save_json_file(self._settings_file_path, self._settings)

    # EQ Curves
    def get_all_custom_eq_curves(self) -> dict[str, list[int]]:
        """Returns a copy of all custom EQ curves."""
        return self._custom_eq_curves.copy()

    def get_custom_eq_curve(self, name: str) -> list[int] | None:
        """Retrieves a specific custom EQ curve by name."""
        return self._custom_eq_curves.get(name)

    def save_custom_eq_curve(self, name: str, values: list[int]) -> None:
        """Saves or updates a custom EQ curve and persists to file."""
        if not (isinstance(values, list) and len(values) == NUM_EQ_BANDS and all(isinstance(v, int) for v in values)):
            logger.error("Invalid EQ curve format for '%s': Must be a list of %d integers.", name, NUM_EQ_BANDS)
            raise ConfigError(f"Invalid EQ curve format for '{name}'.")  # Raise specific error
        self._custom_eq_curves[name] = values
        self._save_json_file(self._custom_eq_curves_file_path, self._custom_eq_curves)

    def delete_custom_eq_curve(self, name: str) -> None:
        """Deletes a custom EQ curve and updates the config file."""
        if name in self._custom_eq_curves:
            del self._custom_eq_curves[name]
            self._save_json_file(
                self._custom_eq_curves_file_path,
                self._custom_eq_curves,
            )
            # If the deleted curve was the active one, reset to default
            if self.get_setting("last_custom_eq_curve_name") == name:
                self.set_setting(
                    "last_custom_eq_curve_name",
                    app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME,
                )
        else:
            logger.warning("Attempted to delete non-existent EQ curve: %s", name)

    # Specific settings shortcuts (no changes needed below this line for paths)
    def get_last_sidetone_level(self) -> int:
        """Gets the last saved sidetone level."""
        return self.get_setting("sidetone_level", app_config.DEFAULT_SIDETONE_LEVEL)

    def set_last_sidetone_level(self, level: int) -> None:
        """Sets and saves the last sidetone level."""
        self.set_setting("sidetone_level", level)

    def get_last_inactive_timeout(self) -> int:
        """Gets the last saved inactive timeout in minutes."""
        return self.get_setting("inactive_timeout", app_config.DEFAULT_INACTIVE_TIMEOUT)

    def set_last_inactive_timeout(self, minutes: int) -> None:
        """Sets and saves the last inactive timeout in minutes."""
        self.set_setting("inactive_timeout", minutes)

    def get_last_active_eq_preset_id(self) -> int:
        """Gets the ID of the last active hardware EQ preset."""
        return self.get_setting("eq_preset_id", app_config.DEFAULT_EQ_PRESET_ID)

    def set_last_active_eq_preset_id(self, preset_id: int) -> None:
        """Sets the last active hardware EQ preset ID and marks EQ type as hardware."""
        self.set_setting("eq_preset_id", preset_id)
        self.set_setting("active_eq_type", "hardware")

    def get_last_custom_eq_curve_name(self) -> str:
        """Gets the name of the last active custom EQ curve."""
        name = self.get_setting(
            "last_custom_eq_curve_name",
            app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME,
        )
        if name not in self._custom_eq_curves and app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME in self._custom_eq_curves:
            logger.warning(
                "Last custom EQ curve '%s' not found, falling back to default '%s'.",
                name,
                app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME,
            )
            return app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME
        if name not in self._custom_eq_curves and self._custom_eq_curves:
            fallback_name = next(iter(self._custom_eq_curves))
            logger.warning(
                "Last custom EQ curve '%s' not found and default also missing, falling back to first available '%s'.",
                name,
                fallback_name,
            )
            return fallback_name
        if name not in self._custom_eq_curves and not self._custom_eq_curves:
            logger.warning(
                "Last custom EQ curve '%s' not found and no custom curves exist, returning name as is.",
                name,
            )
        return name

    def set_last_custom_eq_curve_name(self, name: str) -> None:
        """Sets the last active custom EQ curve name and marks EQ type as custom."""
        self.set_setting("last_custom_eq_curve_name", name)
        self.set_setting("active_eq_type", "custom")

    def get_active_eq_type(self) -> str:  # "hardware" or "custom"
        """Gets the active EQ type ('hardware' or 'custom')."""
        return self.get_setting("active_eq_type", "custom")  # Default to custom EQs
