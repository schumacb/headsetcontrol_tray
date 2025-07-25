"""Unit tests for the ConfigManager class.

This module contains tests for various functionalities of ConfigManager,
including initialization, loading/saving JSON files, handling settings,
and managing custom EQ curves. It uses unittest.mock extensively to
isolate ConfigManager from actual file system operations and dependencies.
"""

import json
import logging
from pathlib import Path
import tempfile  # Added
import unittest
from unittest import mock

import pytest

from headsetcontrol_tray import app_config
from headsetcontrol_tray.config_manager import ConfigManager
from headsetcontrol_tray.exceptions import ConfigError

logging.disable(logging.CRITICAL)

EXPECTED_LOAD_JSON_CALL_COUNT_INIT = 2
EXPECTED_SAVE_CALLS_FOR_DELETE_WITH_RESET = 2
TEST_SIDETONE_LEVEL_VALID = 50
TEST_EQ_PRESET_ID_VALID = 2


class TestConfigManager(unittest.TestCase):
    """Test suite for the ConfigManager class."""

    def setUp(self) -> None:
        """Set up test environment before each test.

        Creates a temporary directory for config files and patches app_config defaults.
        """
        self.temp_dir = tempfile.TemporaryDirectory()
        self.test_config_path = Path(self.temp_dir.name)

        self.expected_settings_file = self.test_config_path / "settings.json"
        self.expected_eq_curves_file = self.test_config_path / "custom_eq_curves.json"

        self.app_config_patcher = mock.patch.multiple(
            app_config,
            # CONFIG_DIR, CONFIG_FILE, CUSTOM_EQ_CURVES_FILE removed
            DEFAULT_EQ_CURVES={"DefaultFlat": [0] * 10},
            DEFAULT_CUSTOM_EQ_CURVE_NAME="DefaultFlat",
            DEFAULT_SIDETONE_LEVEL=64,
            DEFAULT_EQ_PRESET_ID=0,
            DEFAULT_INACTIVE_TIMEOUT=15,
        )
        self.mocked_app_config = self.app_config_patcher.start()

        self.CM_DEFAULT_ACTIVE_EQ_TYPE = "custom"
        self.CM_DEFAULT_CHATMIX_ENABLED = True

    def tearDown(self) -> None:
        """Clean up test environment after each test.

        Stops patches and removes the temporary directory.
        """
        self.app_config_patcher.stop()
        self.temp_dir.cleanup()  # Clean up TemporaryDirectory

    @mock.patch.object(ConfigManager, "_load_json_file")
    @mock.patch.object(ConfigManager, "_save_json_file")
    @mock.patch("headsetcontrol_tray.config_manager.Path.mkdir")  # Patch Path.mkdir directly in the module
    def test_init_paths_created_and_loaded(
        self,
        mock_path_mkdir: mock.MagicMock,
        mock_save_json: mock.MagicMock,
        mock_load_json: mock.MagicMock,
    ) -> None:
        """Test ConfigManager initialization creates paths and loads existing files."""
        mock_load_json.side_effect = [{"some_setting": "value"}, {"MyCurve": [0] * 10}]  # 10 bands

        cm = ConfigManager(config_dir_path=self.test_config_path)

        # Check that config_dir_path.mkdir was called.
        # Path.mkdir is patched, so it's called on the Path class, not instance.
        # The instance `self._config_dir` calls `self._config_dir.mkdir()`.
        # So, we need to ensure the mock `Path(self.test_config_path).mkdir` was called.
        # This is tricky. A simpler approach is to mock the `mkdir` method of the specific Path instance.
        # However, the current mock `mock_path_mkdir` will catch the call if it's `Path.mkdir`.
        # If `ConfigManager` does `self._config_dir.mkdir()`, then `mock_path_mkdir` as `Path.mkdir` is not right.
        # Let's assume ConfigManager does `self._config_dir.mkdir()`.
        # We should patch `self.test_config_path.mkdir` or ensure the directory is made.
        # For this test, let's assert that the directory *exists* if not mocking mkdir specifically for the instance.
        # Or, if `Path.mkdir` is what's patched globally, then the call is on the class.
        # The code is `self._config_dir.mkdir(...)`. So we should patch the instance.
        # To avoid this complexity, we can check `self.test_config_path.exists()` if `mkdir` is not mocked,
        # or mock `self.test_config_path.mkdir` specifically.
        # Given the current mock setup, `Path.mkdir` is globally mocked.
        # This means any `some_path_obj.mkdir()` will resolve to the same global mock.

        # This assertion is fine if Path.mkdir is globally mocked.
        mock_path_mkdir.assert_called_once_with(parents=True, exist_ok=True)

        assert mock_load_json.call_count == EXPECTED_LOAD_JSON_CALL_COUNT_INIT
        mock_load_json.assert_any_call(self.expected_settings_file)
        mock_load_json.assert_any_call(self.expected_eq_curves_file)
        assert cm.get_setting("some_setting") == "value"
        assert cm.get_all_custom_eq_curves() == {"MyCurve": [0] * 10}
        mock_save_json.assert_not_called()

    @mock.patch.object(ConfigManager, "_load_json_file")
    @mock.patch.object(ConfigManager, "_save_json_file")
    @mock.patch("headsetcontrol_tray.config_manager.Path.mkdir")  # Patch Path.mkdir globally
    @mock.patch("headsetcontrol_tray.config_manager.Path.exists", return_value=True)  # Patch Path.exists globally
    def test_init_default_eq_curves_saved_if_empty(
        self,
        mock_path_exists: mock.MagicMock,
        mock_path_mkdir: mock.MagicMock,
        mock_save_json: mock.MagicMock,
        mock_load_json: mock.MagicMock,
    ) -> None:
        """Test that default EQ curves are saved if the EQ file is initially empty."""
        mock_load_json.side_effect = [{"some_setting": "value"}, {}]  # EQ file is empty

        # self.test_config_path.exists() will be caught by mock_path_exists
        cm = ConfigManager(config_dir_path=self.test_config_path)

        mock_path_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        mock_path_exists.assert_any_call()  # Path.exists is called
        assert mock_load_json.call_count == EXPECTED_LOAD_JSON_CALL_COUNT_INIT
        assert cm.get_all_custom_eq_curves() == app_config.DEFAULT_EQ_CURVES
        mock_save_json.assert_called_once_with(
            self.expected_eq_curves_file,
            app_config.DEFAULT_EQ_CURVES,
        )

    @mock.patch("json.load")
    def test_load_json_file_success(self, mock_json_load: mock.MagicMock) -> None:
        """Test successful loading of a JSON file."""
        mock_file_path = mock.MagicMock(spec=Path)
        mock_file_path.exists.return_value = True
        expected_data = {"key": "value"}
        mock_json_load.return_value = expected_data
        # mock_open needs to be attached to the mock_file_path instance
        mock_file_path.open = mock.mock_open(read_data=json.dumps(expected_data))

        with mock.patch.object(ConfigManager, "__init__", return_value=None):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            loaded_data = cm._load_json_file(mock_file_path)  # noqa: SLF001 # Testing protected method

        mock_file_path.exists.assert_called_once()
        mock_file_path.open.assert_called_once_with("r", encoding="utf-8")
        mock_json_load.assert_called_once()
        assert loaded_data == expected_data

    @mock.patch("json.load", side_effect=json.JSONDecodeError("Error", "doc", 0))
    def test_load_json_file_decode_error(self, mock_json_load_with_side_effect: mock.MagicMock) -> None:  # noqa: ARG002 # Mock carries side effect
        """Test handling of JSONDecodeError when loading a file."""
        mock_file_path = mock.MagicMock(spec=Path)
        mock_file_path.exists.return_value = True
        mock_file_path.open = mock.mock_open()

        with (
            mock.patch.object(ConfigManager, "__init__", return_value=None),
            mock.patch("headsetcontrol_tray.config_manager.logger") as mock_logger,
        ):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            loaded_data = cm._load_json_file(mock_file_path)  # noqa: SLF001 # Testing protected method
        mock_logger.exception.assert_called_once_with(
            "Failed to decode JSON from file %s. Using empty config for this file.",
            mock_file_path,
        )
        assert loaded_data == {}

    def test_load_json_file_does_not_exist(self) -> None:
        """Test behavior when loading a JSON file that does not exist."""
        mock_file_path = mock.MagicMock(spec=Path)
        mock_file_path.exists.return_value = False
        with mock.patch.object(ConfigManager, "__init__", return_value=None):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            loaded_data = cm._load_json_file(mock_file_path)  # noqa: SLF001 # Testing protected method
        assert loaded_data == {}

    @mock.patch("json.dump")
    def test_save_json_file_success(self, mock_json_dump: mock.MagicMock) -> None:
        """Test successful saving of data to a JSON file."""
        mock_file_path = mock.MagicMock(spec=Path)
        data_to_save = {"key": "value"}
        mock_file_path.open = mock.mock_open()

        with mock.patch.object(ConfigManager, "__init__", return_value=None):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            # For _save_json_file's check: `if not self._config_dir.exists():`
            cm._config_dir = mock.MagicMock(spec=Path)  # noqa: SLF001 # Mocking internal attribute for test
            cm._config_dir.exists.return_value = True  # noqa: SLF001 # Mocking internal attribute for test

            cm._save_json_file(mock_file_path, data_to_save)  # noqa: SLF001 # Testing protected method

        mock_file_path.open.assert_called_once_with("w", encoding="utf-8")
        mock_json_dump.assert_called_once_with(
            data_to_save,
            mock_file_path.open.return_value,  # Get the mock file handle from mock_open
            indent=4,
        )

    @mock.patch("json.dump")  # Mock dump to prevent it from running if open fails
    def test_save_json_file_io_error_on_open(self, mock_json_dump: mock.MagicMock) -> None:
        """Test handling of OSError when opening a file for saving."""
        mock_file_path = mock.MagicMock(spec=Path)
        data_to_save = {"key": "value"}
        mock_file_path.open = mock.Mock(side_effect=OSError("Disk full"))

        with (
            mock.patch.object(ConfigManager, "__init__", return_value=None),
            mock.patch("headsetcontrol_tray.config_manager.logger") as mock_logger,
        ):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm._config_dir = mock.MagicMock(spec=Path)  # noqa: SLF001 # Mocking internal attribute for test
            cm._config_dir.exists.return_value = True  # noqa: SLF001 # Mocking internal attribute for test

            cm._save_json_file(mock_file_path, data_to_save)  # noqa: SLF001 # Testing protected method

        mock_json_dump.assert_not_called()
        mock_logger.exception.assert_called_once_with("Error saving JSON file %s", mock_file_path)

    @mock.patch("json.dump", side_effect=OSError("Permission denied"))
    def test_save_json_file_os_error_on_dump(self, mock_json_dump_raises_oserror: mock.MagicMock) -> None:
        """Test handling of OSError during json.dump."""
        mock_file_path = mock.MagicMock(spec=Path)
        data_to_save = {"key": "value"}
        mock_file_path.open = mock.mock_open()

        with (
            mock.patch.object(ConfigManager, "__init__", return_value=None),
            mock.patch("headsetcontrol_tray.config_manager.logger") as mock_logger,
        ):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm._config_dir = mock.MagicMock(spec=Path)  # noqa: SLF001 # Mocking internal attribute for test
            cm._config_dir.exists.return_value = True  # noqa: SLF001 # Mocking internal attribute for test

            cm._save_json_file(mock_file_path, data_to_save)  # noqa: SLF001 # Testing protected method

        mock_json_dump_raises_oserror.assert_called_once()
        mock_logger.exception.assert_called_once_with("Error saving JSON file %s", mock_file_path)

    def test_get_setting(self) -> None:
        """Test retrieving settings with and without defaults."""
        with mock.patch.object(ConfigManager, "__init__", return_value=None):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm._settings = {"existing_key": "existing_value"}  # noqa: SLF001 # Setting internal state for test
        assert cm.get_setting("existing_key") == "existing_value"
        assert cm.get_setting("non_existing_key", "default_val") == "default_val"
        assert cm.get_setting("non_existing_key") is None

    @mock.patch.object(ConfigManager, "_save_json_file")
    def test_set_setting(self, mock_save_json: mock.MagicMock) -> None:
        """Test setting a value and that it triggers a save."""
        with mock.patch.object(ConfigManager, "__init__", return_value=None):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm._settings_file_path = self.expected_settings_file  # noqa: SLF001 # Setting internal state for test
            cm._settings = {}  # noqa: SLF001 # Setting internal state for test
            cm._config_dir = mock.MagicMock(spec=Path)  # noqa: SLF001 # Mocking internal attribute for test
            cm._config_dir.exists.return_value = True  # noqa: SLF001 # Mocking internal attribute for test

        cm.set_setting("test_key", "test_value")
        assert cm.get_setting("test_key") == "test_value"
        mock_save_json.assert_called_once_with(self.expected_settings_file, {"test_key": "test_value"})

    def test_get_all_custom_eq_curves(self) -> None:
        """Test retrieving all custom EQ curves, ensuring a copy is returned."""
        test_curves = {"Curve1": [0] * 10}
        with mock.patch.object(ConfigManager, "__init__", return_value=None):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm._custom_eq_curves = test_curves.copy()  # noqa: SLF001 # Setting internal state for test

        retrieved_curves = cm.get_all_custom_eq_curves()
        assert retrieved_curves == test_curves
        retrieved_curves["NewKey"] = [1] * 10  # Modify returned
        assert cm.get_all_custom_eq_curves() == test_curves  # Original should be unchanged

    def test_get_custom_eq_curve(self) -> None:
        """Test retrieving a specific custom EQ curve by name."""
        test_curves = {"Curve1": [0] * 10}
        with mock.patch.object(ConfigManager, "__init__", return_value=None):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm._custom_eq_curves = test_curves  # noqa: SLF001 # Setting internal state for test
        assert cm.get_custom_eq_curve("Curve1") == [0] * 10
        assert cm.get_custom_eq_curve("NonExistent") is None

    def test_save_custom_eq_curve_validation(self) -> None:
        """Test validation when saving custom EQ curves (length and type)."""
        with mock.patch.object(ConfigManager, "__init__", return_value=None):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm._custom_eq_curves = {}  # noqa: SLF001 # Setting internal state for test
        with pytest.raises(
            ConfigError,
            match=r"Invalid EQ values.",
        ):
            cm.save_custom_eq_curve("InvalidCurveShort", [0] * 5)
        with pytest.raises(ConfigError, match=r"Invalid EQ values."):
            cm.save_custom_eq_curve("InvalidCurveType", ["a"] * 10)  # type: ignore[list-item]

    @mock.patch.object(ConfigManager, "_save_json_file")
    def test_save_custom_eq_curve_success(self, mock_save_json: mock.MagicMock) -> None:
        """Test successfully saving a valid custom EQ curve."""
        with mock.patch.object(ConfigManager, "__init__", return_value=None):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm._custom_eq_curves_file_path = self.expected_eq_curves_file  # noqa: SLF001 # Setting internal state for test
            cm._custom_eq_curves = {"ExistingCurve": [0] * 10}  # noqa: SLF001 # Setting internal state for test
            cm._config_dir = mock.MagicMock(spec=Path)  # noqa: SLF001 # Mocking internal attribute for test
            cm._config_dir.exists.return_value = True  # noqa: SLF001 # Mocking internal attribute for test

        new_curve_name = "NewCurve"
        new_curve_values = [1] * 10
        cm.save_custom_eq_curve(new_curve_name, new_curve_values)
        assert cm.get_custom_eq_curve(new_curve_name) == new_curve_values
        expected_curves_after_save = {"ExistingCurve": [0] * 10, new_curve_name: new_curve_values}
        mock_save_json.assert_called_with(  # Use assert_called_with for last call or specific call
            self.expected_eq_curves_file,
            expected_curves_after_save,
        )

    @mock.patch.object(ConfigManager, "_save_json_file")
    def test_delete_custom_eq_curve(self, mock_save_json: mock.MagicMock) -> None:
        """Test deleting a custom EQ curve and its side effects on settings."""
        with mock.patch.object(ConfigManager, "__init__", return_value=None):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm._settings_file_path = self.expected_settings_file  # noqa: SLF001 # Setting internal state for test
            cm._custom_eq_curves_file_path = self.expected_eq_curves_file  # noqa: SLF001 # Setting internal state for test
            cm._config_dir = mock.MagicMock(spec=Path)  # noqa: SLF001 # Mocking internal attribute for test
            cm._config_dir.exists.return_value = True  # noqa: SLF001 # Mocking internal attribute for test

            cm._custom_eq_curves = {  # noqa: SLF001 # Setting internal state for test
                "ToDelete": [0] * 10,
                "ToKeep": [1] * 10,
                app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME: [0] * 10,
            }
            # Simulate set_setting being part of the same ConfigManager instance
            cm._settings = {"last_custom_eq_curve_name": "ToDelete", "active_eq_type": "Custom"}  # noqa: SLF001 # Setting internal state

        cm.delete_custom_eq_curve("ToDelete")
        assert cm.get_custom_eq_curve("ToDelete") is None
        expected_curves_after_delete1 = {"ToKeep": [1] * 10, app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME: [0] * 10}

        # Check calls to _save_json_file
        # One for eq_curves, one for settings (due to set_setting call)
        assert mock_save_json.call_count == EXPECTED_SAVE_CALLS_FOR_DELETE_WITH_RESET
        mock_save_json.assert_any_call(self.expected_eq_curves_file, expected_curves_after_delete1)
        # The settings dict would be updated by the set_setting call inside delete_custom_eq_curve
        expected_settings_after_delete = {
            "last_custom_eq_curve_name": app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME,
            "active_eq_type": "Custom",  # Assuming set_setting doesn't change this unless explicitly told
        }
        mock_save_json.assert_any_call(self.expected_settings_file, expected_settings_after_delete)

        assert cm.get_setting("last_custom_eq_curve_name") == app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME

        mock_save_json.reset_mock()
        # Reset settings for the next part of the test
        cm._settings = {"last_custom_eq_curve_name": "OtherCurve"}  # noqa: SLF001 # Setting internal state for test

        cm.delete_custom_eq_curve("ToKeep")
        assert cm.get_custom_eq_curve("ToKeep") is None
        assert cm.get_setting("last_custom_eq_curve_name") == "OtherCurve"  # Should not change if not "ToKeep"
        expected_curves_after_delete2 = {app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME: [0] * 10}
        mock_save_json.assert_called_once_with(
            self.expected_eq_curves_file,
            expected_curves_after_delete2,
        )

    def test_get_last_sidetone_level(self) -> None:
        """Test retrieving the last sidetone level."""
        with mock.patch.object(ConfigManager, "get_setting") as mock_get_setting:
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm.get_last_sidetone_level()
        mock_get_setting.assert_called_once_with("sidetone_level", app_config.DEFAULT_SIDETONE_LEVEL)

    def test_set_last_sidetone_level(self) -> None:
        """Test setting the last sidetone level."""
        with mock.patch.object(ConfigManager, "set_setting") as mock_set_setting:
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm.set_last_sidetone_level(TEST_SIDETONE_LEVEL_VALID)
        mock_set_setting.assert_called_once_with("sidetone_level", TEST_SIDETONE_LEVEL_VALID)

    def test_get_last_inactive_timeout(self) -> None:
        """Test retrieving the last inactive timeout setting."""
        with mock.patch.object(ConfigManager, "get_setting") as mock_get_setting:
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm.get_last_inactive_timeout()
        mock_get_setting.assert_called_once_with("inactive_timeout", app_config.DEFAULT_INACTIVE_TIMEOUT)

    def test_set_last_inactive_timeout(self) -> None:
        """Test setting the last inactive timeout."""
        with mock.patch.object(ConfigManager, "set_setting") as mock_set_setting:
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm.set_last_inactive_timeout(30)
        mock_set_setting.assert_called_once_with("inactive_timeout", 30)

    def test_get_last_active_eq_preset_id(self) -> None:
        """Test retrieving the last active hardware EQ preset ID."""
        with mock.patch.object(ConfigManager, "get_setting") as mock_get_setting:
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm.get_last_active_eq_preset_id()
        mock_get_setting.assert_called_once_with("eq_preset_id", app_config.DEFAULT_EQ_PRESET_ID)

    def test_set_last_active_eq_preset_id(self) -> None:
        """Test setting the last active hardware EQ preset ID."""
        with mock.patch.object(ConfigManager, "set_setting") as mock_set_setting:
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm.set_last_active_eq_preset_id(TEST_EQ_PRESET_ID_VALID)
        mock_set_setting.assert_any_call("eq_preset_id", TEST_EQ_PRESET_ID_VALID)
        mock_set_setting.assert_any_call("active_eq_type", "hardware")
        assert mock_set_setting.call_count == EXPECTED_SAVE_CALLS_FOR_DELETE_WITH_RESET

    def test_get_last_custom_eq_curve_name_fallbacks(self) -> None:
        """Test fallback logic for retrieving the last custom EQ curve name."""
        # Test with __init__ not mocked to allow _custom_eq_curves to be initialized
        # but mock _load_json_file to control what's "loaded"
        with (
            mock.patch.object(ConfigManager, "_load_json_file") as mock_load_json,
            mock.patch.object(ConfigManager, "_save_json_file"),  # Testing protected method
        ):  # Mock save to prevent writes
            # Scenario 1: Last saved name exists in curves
            mock_load_json.side_effect = [
                {"last_custom_eq_curve_name": "ExistingCurve"},  # settings
                {"ExistingCurve": [0] * 10, app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME: [1] * 10},
            ]
            cm = ConfigManager(config_dir_path=self.test_config_path)
            assert cm.get_last_custom_eq_curve_name() == "ExistingCurve"

            # Scenario 2: Last saved name does NOT exist, default exists
            mock_load_json.reset_mock(side_effect=True)
            mock_load_json.side_effect = [
                {"last_custom_eq_curve_name": "MissingCurve"},  # settings
                {app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME: [1] * 10, "AnotherCurve": [2] * 10},
            ]
            cm = ConfigManager(config_dir_path=self.test_config_path)
            assert cm.get_last_custom_eq_curve_name() == app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME

            # Scenario 3: Last saved name does NOT exist, default also MISSING, fallback to first available
            mock_load_json.reset_mock(side_effect=True)
            mock_load_json.side_effect = [
                {"last_custom_eq_curve_name": "MissingCurve"},  # settings
                {"FirstAvailable": [0] * 10, "AnotherCurve": [2] * 10},  # curves (default is missing)
            ]
            cm = ConfigManager(config_dir_path=self.test_config_path)
            assert cm.get_last_custom_eq_curve_name() == "FirstAvailable"

            # Scenario 4: No curves exist at all (e.g. fresh init, save failed)
            mock_load_json.reset_mock(side_effect=True)
            mock_load_json.side_effect = [
                {"last_custom_eq_curve_name": "AnyName"},  # settings
                {},  # No curves
            ]
            # For this, we also need to ensure DEFAULT_EQ_CURVES is empty to simulate no defaults being populated
            with mock.patch.object(app_config, "DEFAULT_EQ_CURVES", {}):  # Patched app_config directly
                cm = ConfigManager(config_dir_path=self.test_config_path)
                assert cm.get_last_custom_eq_curve_name() == "AnyName"  # Returns the name as is
        # Removed cm.set_last_custom_eq_curve_name and subsequent mock_set_setting assertions from this test method.

    def test_get_active_eq_type(self) -> None:
        """Test retrieving the active EQ type (hardware or custom)."""
        with mock.patch.object(ConfigManager, "get_setting") as mock_get_setting:
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm.get_active_eq_type()
        mock_get_setting.assert_called_once_with(
            "active_eq_type",
            self.CM_DEFAULT_ACTIVE_EQ_TYPE,
        )  # Reverted to self.CM_DEFAULT

    # Test default values for other specific settings
    def test_default_chatmix_enabled(self) -> None:
        """Test the default value for chatmix_enabled setting."""
        with mock.patch.object(ConfigManager, "get_setting") as mock_get_setting:
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm.get_setting("chatmix_enabled", self.CM_DEFAULT_CHATMIX_ENABLED)  # Reverted to self.CM_DEFAULT
        mock_get_setting.assert_called_once_with(
            "chatmix_enabled",
            self.CM_DEFAULT_CHATMIX_ENABLED,
        )  # Reverted to self.CM_DEFAULT

    # ... (similar tests for other defaults can be added if they have specific getters/setters) ...

    def test_config_dir_creation_failure(self) -> None:
        """Test that an error during config directory creation is logged."""
        # Test that an error during directory creation is logged
        with (
            mock.patch(
                "headsetcontrol_tray.config_manager.Path.mkdir",
                side_effect=OSError("Cannot create dir"),
            ) as mock_mkdir,
            mock.patch("headsetcontrol_tray.config_manager.logger") as mock_logger,
            mock.patch.object(ConfigManager, "_load_json_file", return_value={}),  # Testing protected method
            mock.patch.object(ConfigManager, "_save_json_file"),  # Testing protected method
        ):  # Mock save to prevent issues if load fails
            # The variable 'config_manager' was unused.
            ConfigManager(config_dir_path=self.test_config_path)
            # Check that the mock_mkdir was called
            mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)
            # Check that logger.exception was called with the correct message format and arguments
            mock_logger.exception.assert_called_once_with(
                "Could not create config directory %s",
                self.test_config_path,
                # This is how you match the exception instance when it's part of the log message
                # The original code logs `f"... {e}"`, so we expect the exception
                # instance as the last arg to logger.exception.
                # However, logger.exception(message, *args, exc_info=...) - if exc_info is
                # True (default for .exception) the exception is handled automatically.
                # If we pass the exception as an arg in the message,
                # it should be `logger.exception("message with %s", e)`.
                # The code is `logger.exception(f"Could not create config directory {self._config_dir}: {e}")`
                # This means the exception `e` is formatted into the message string itself.
                # So, we don't need to pass `unittest.mock.ANY` as a separate argument here.
                # The f-string formatting in the assert_called_once_with should match the logged string.
            )

    def test_init_default_eq_curves_not_saved_if_dir_creation_fails(
        self,
    ) -> None:
        """Test that default EQ curves are not saved if config directory creation fails."""
        with (
            mock.patch.object(ConfigManager, "_load_json_file", return_value={}),  # Testing protected method
            mock.patch.object(ConfigManager, "_save_json_file") as mock_save_json,  # Testing protected method
            mock.patch(
                "headsetcontrol_tray.config_manager.Path.mkdir",
                side_effect=OSError("Cannot create dir"),
            ) as mock_path_mkdir_global,
            mock.patch("headsetcontrol_tray.config_manager.Path.exists", return_value=False),  # Removed F841
            mock.patch("headsetcontrol_tray.config_manager.logger") as mock_logger,
        ):
            cm = ConfigManager(config_dir_path=self.test_config_path)  # Instantiate only once

            # 1. Check that Path.mkdir was called (and raised an error)
            mock_path_mkdir_global.assert_called_once_with(parents=True, exist_ok=True)

            # 2. Check that logger.exception was called due to mkdir failure
            mock_logger.exception.assert_called_once_with("Could not create config directory %s", self.test_config_path)
            # 3. Check that logger.warning was called because dir doesn't exist for saving defaults
            mock_logger.warning.assert_called_once_with(
                "Config directory does not exist. Skipping initial save of default EQ curves.",
            )

            # 4. Ensure _save_json_file was NOT called for the default EQ curves file
            # Removed F841 by removing save_calls assignment
            found_eq_curves_save_call = False
            for call_args_tuple in mock_save_json.call_args_list:
                if call_args_tuple[0][0] == self.expected_eq_curves_file:
                    found_eq_curves_save_call = True
                    break
            assert not found_eq_curves_save_call, (
                "_save_json_file should not have been called for default EQ curves if directory does not exist."
            )

            # 5. The _custom_eq_curves attribute should still be populated with app_config defaults
            assert cm._custom_eq_curves == app_config.DEFAULT_EQ_CURVES, (  # noqa: SLF001 # Verifying internal state
                "cm._custom_eq_curves should be populated from app_config defaults even if save is skipped."
            )
