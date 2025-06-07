import json
import logging
from pathlib import Path
from typing import Any

from . import app_config

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")

class ConfigManager:
    """Manages application settings and custom EQ curves persistence."""

    def __init__(self):
        app_config.CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self._settings: dict[str, Any] = self._load_json_file(app_config.CONFIG_FILE)
        self._custom_eq_curves: dict[str, list[int]] = self._load_json_file(app_config.CUSTOM_EQ_CURVES_FILE)

        if not self._custom_eq_curves: # Initialize with defaults if empty
            self._custom_eq_curves = app_config.DEFAULT_EQ_CURVES.copy()
            self._save_json_file(app_config.CUSTOM_EQ_CURVES_FILE, self._custom_eq_curves)

    def _load_json_file(self, file_path: Path) -> dict:
        if file_path.exists():
            try:
                with open(file_path) as f:
                    return json.load(f)
            except json.JSONDecodeError:
                logger.warning(f"Could not decode JSON from {file_path}. Using empty config.")
                return {}
        return {}

    def _save_json_file(self, file_path: Path, data: dict) -> None:
        try:
            with open(file_path, "w") as f:
                json.dump(data, f, indent=4)
        except OSError:
            logger.error(f"Could not write to {file_path}.")


    # General Settings
    def get_setting(self, key: str, default: Any = None) -> Any:
        return self._settings.get(key, default)

    def set_setting(self, key: str, value: Any) -> None:
        self._settings[key] = value
        self._save_json_file(app_config.CONFIG_FILE, self._settings)

    # EQ Curves
    def get_all_custom_eq_curves(self) -> dict[str, list[int]]:
        return self._custom_eq_curves.copy()

    def get_custom_eq_curve(self, name: str) -> list[int] | None:
        return self._custom_eq_curves.get(name)

    def save_custom_eq_curve(self, name: str, values: list[int]) -> None:
        if not (isinstance(values, list) and len(values) == 10 and all(isinstance(v, int) for v in values)):
            raise ValueError("EQ curve must be a list of 10 integers.")
        self._custom_eq_curves[name] = values
        self._save_json_file(app_config.CUSTOM_EQ_CURVES_FILE, self._custom_eq_curves)

    def delete_custom_eq_curve(self, name: str) -> None:
        if name in self._custom_eq_curves:
            del self._custom_eq_curves[name]
            self._save_json_file(app_config.CUSTOM_EQ_CURVES_FILE, self._custom_eq_curves)
            # If the deleted curve was the active one, reset to default
            if self.get_setting("last_custom_eq_curve_name") == name:
                self.set_setting("last_custom_eq_curve_name", app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME)


    # Specific settings shortcuts
    def get_last_sidetone_level(self) -> int:
        return self.get_setting("sidetone_level", app_config.DEFAULT_SIDETONE_LEVEL)

    def set_last_sidetone_level(self, level: int) -> None:
        self.set_setting("sidetone_level", level)

    def get_last_inactive_timeout(self) -> int:
        return self.get_setting("inactive_timeout", app_config.DEFAULT_INACTIVE_TIMEOUT)

    def set_last_inactive_timeout(self, minutes: int) -> None:
        self.set_setting("inactive_timeout", minutes)

    def get_last_active_eq_preset_id(self) -> int:
        return self.get_setting("eq_preset_id", app_config.DEFAULT_EQ_PRESET_ID)

    def set_last_active_eq_preset_id(self, preset_id: int) -> None:
        self.set_setting("eq_preset_id", preset_id)
        self.set_setting("active_eq_type", "hardware")


    def get_last_custom_eq_curve_name(self) -> str:
        # Ensure the stored curve name still exists, otherwise fallback to default
        name = self.get_setting("last_custom_eq_curve_name", app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME)
        if name not in self._custom_eq_curves and app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME in self._custom_eq_curves:
            return app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME
        if name not in self._custom_eq_curves and self._custom_eq_curves: # fallback to first available if default also gone
            return next(iter(self._custom_eq_curves))
        return name

    def set_last_custom_eq_curve_name(self, name: str) -> None:
        self.set_setting("last_custom_eq_curve_name", name)
        self.set_setting("active_eq_type", "custom")

    def get_active_eq_type(self) -> str: # "hardware" or "custom"
        return self.get_setting("active_eq_type", "custom") # Default to custom EQs
