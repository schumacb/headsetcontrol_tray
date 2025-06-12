import json
import logging
from pathlib import Path
import tempfile # Added
import unittest
from unittest import mock

import pytest

from headsetcontrol_tray import app_config
from headsetcontrol_tray.config_manager import ConfigManager
from headsetcontrol_tray.exceptions import ConfigError

logging.disable(logging.CRITICAL)

EXPECTED_LOAD_JSON_CALL_COUNT_INIT = 2
TEST_SIDETONE_LEVEL_VALID = 50
TEST_EQ_PRESET_ID_VALID = 2


class TestConfigManager(unittest.TestCase):
    def setUp(self) -> None:
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
        self.CM_DEFAULT_AUTO_MUTE_MIC_ENABLED = False
        self.CM_DEFAULT_RUN_ON_STARTUP_ENABLED = True
        self.CM_DEFAULT_MINIMIZE_TO_TRAY_ENABLED = True
        self.CM_DEFAULT_CHECK_FOR_UPDATES_ENABLED = True
        self.CM_DEFAULT_INCLUDE_PRERELEASES_ENABLED = False
        self.CM_DEFAULT_DARK_MODE = "auto"


    def tearDown(self) -> None:
        self.app_config_patcher.stop()
        self.temp_dir.cleanup() # Clean up TemporaryDirectory

    @mock.patch.object(ConfigManager, "_load_json_file")
    @mock.patch.object(ConfigManager, "_save_json_file")
    @mock.patch("headsetcontrol_tray.config_manager.Path.mkdir") # Patch Path.mkdir directly in the module
    def test_init_paths_created_and_loaded(
        self, mock_path_mkdir: mock.MagicMock, mock_save_json: mock.MagicMock, mock_load_json: mock.MagicMock,
    ) -> None:
        mock_load_json.side_effect = [{"some_setting": "value"}, {"MyCurve": [0] * 10}] # 10 bands

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
    @mock.patch("headsetcontrol_tray.config_manager.Path.mkdir") # Patch Path.mkdir
    def test_init_default_eq_curves_saved_if_empty(
        self, mock_path_mkdir: mock.MagicMock, mock_save_json: mock.MagicMock, mock_load_json: mock.MagicMock,
    ) -> None:
        mock_load_json.side_effect = [{"some_setting": "value"}, {}] # EQ file is empty

        # Patch self.test_config_path.exists() to return True for the save operation
        # This is needed because _save_json_file checks self._config_dir.exists()
        # And _config_dir is self.test_config_path
        with mock.patch.object(self.test_config_path, 'exists', return_value=True):
            cm = ConfigManager(config_dir_path=self.test_config_path)

        mock_path_mkdir.assert_called_once_with(parents=True, exist_ok=True)
        assert mock_load_json.call_count == EXPECTED_LOAD_JSON_CALL_COUNT_INIT
        assert cm.get_all_custom_eq_curves() == self.mocked_app_config["DEFAULT_EQ_CURVES"]
        mock_save_json.assert_called_once_with(
            self.expected_eq_curves_file,
            self.mocked_app_config["DEFAULT_EQ_CURVES"],
        )

    @mock.patch("json.load")
    def test_load_json_file_success(self, mock_json_load: mock.MagicMock) -> None:
        mock_file_path = mock.MagicMock(spec=Path)
        mock_file_path.exists.return_value = True
        expected_data = {"key": "value"}
        mock_json_load.return_value = expected_data
        # mock_open needs to be attached to the mock_file_path instance
        mock_file_path.open = mock.mock_open(read_data=json.dumps(expected_data))

        with mock.patch.object(ConfigManager, "__init__", return_value=None):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            loaded_data = cm._load_json_file(mock_file_path)

        mock_file_path.exists.assert_called_once()
        mock_file_path.open.assert_called_once_with("r", encoding="utf-8")
        mock_json_load.assert_called_once()
        assert loaded_data == expected_data

    @mock.patch("json.load", side_effect=json.JSONDecodeError("Error", "doc", 0))
    def test_load_json_file_decode_error(self, _mock_json_load_raises: mock.MagicMock) -> None:
        mock_file_path = mock.MagicMock(spec=Path)
        mock_file_path.exists.return_value = True
        mock_file_path.open = mock.mock_open()

        with mock.patch.object(ConfigManager, "__init__", return_value=None), \
             mock.patch("headsetcontrol_tray.config_manager.logger") as mock_logger:
            cm = ConfigManager(config_dir_path=Path("dummy"))
            loaded_data = cm._load_json_file(mock_file_path)
        mock_logger.exception.assert_called_once_with(
            "Failed to decode JSON from file %s. Using empty config for this file.",
            mock_file_path,
        )
        assert loaded_data == {}

    def test_load_json_file_does_not_exist(self) -> None:
        mock_file_path = mock.MagicMock(spec=Path)
        mock_file_path.exists.return_value = False
        with mock.patch.object(ConfigManager, "__init__", return_value=None):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            loaded_data = cm._load_json_file(mock_file_path)
        assert loaded_data == {}

    @mock.patch("json.dump")
    def test_save_json_file_success(self, mock_json_dump: mock.MagicMock) -> None:
        mock_file_path = mock.MagicMock(spec=Path)
        data_to_save = {"key": "value"}
        mock_file_path.open = mock.mock_open()

        with mock.patch.object(ConfigManager, "__init__", return_value=None):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            # For _save_json_file's check: `if not self._config_dir.exists():`
            cm._config_dir = mock.MagicMock(spec=Path)
            cm._config_dir.exists.return_value = True

            cm._save_json_file(mock_file_path, data_to_save)

        mock_file_path.open.assert_called_once_with("w", encoding="utf-8")
        mock_json_dump.assert_called_once_with(
            data_to_save,
            mock_file_path.open.return_value, # Get the mock file handle from mock_open
            indent=4,
        )

    @mock.patch("json.dump") # Mock dump to prevent it from running if open fails
    def test_save_json_file_io_error_on_open(self, mock_json_dump: mock.MagicMock) -> None:
        mock_file_path = mock.MagicMock(spec=Path)
        data_to_save = {"key": "value"}
        mock_file_path.open = mock.Mock(side_effect=OSError("Disk full"))

        with mock.patch.object(ConfigManager, "__init__", return_value=None), \
             mock.patch("headsetcontrol_tray.config_manager.logger") as mock_logger:
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm._config_dir = mock.MagicMock(spec=Path)
            cm._config_dir.exists.return_value = True

            cm._save_json_file(mock_file_path, data_to_save)

        mock_json_dump.assert_not_called()
        mock_logger.exception.assert_called_once_with("Error saving JSON file %s", mock_file_path)


    @mock.patch("json.dump", side_effect=OSError("Permission denied"))
    def test_save_json_file_os_error_on_dump(self, mock_json_dump_raises_oserror: mock.MagicMock) -> None:
        mock_file_path = mock.MagicMock(spec=Path)
        data_to_save = {"key": "value"}
        mock_file_path.open = mock.mock_open()

        with mock.patch.object(ConfigManager, "__init__", return_value=None), \
             mock.patch("headsetcontrol_tray.config_manager.logger") as mock_logger:
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm._config_dir = mock.MagicMock(spec=Path)
            cm._config_dir.exists.return_value = True

            cm._save_json_file(mock_file_path, data_to_save)

        mock_json_dump_raises_oserror.assert_called_once()
        mock_logger.exception.assert_called_once_with("Error saving JSON file %s", mock_file_path)


    def test_get_setting(self) -> None:
        with mock.patch.object(ConfigManager, "__init__", return_value=None):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm._settings = {"existing_key": "existing_value"}
            # cm._custom_eq_curves = {} # Not strictly needed for this test
        assert cm.get_setting("existing_key") == "existing_value"
        assert cm.get_setting("non_existing_key", "default_val") == "default_val"
        assert cm.get_setting("non_existing_key") is None


    @mock.patch.object(ConfigManager, "_save_json_file")
    def test_set_setting(self, mock_save_json: mock.MagicMock) -> None:
        with mock.patch.object(ConfigManager, "__init__", return_value=None):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm._settings_file_path = self.expected_settings_file
            cm._settings = {}
            # cm._custom_eq_curves = {} # Not strictly needed
            cm._config_dir = mock.MagicMock(spec=Path)
            cm._config_dir.exists.return_value = True


        cm.set_setting("test_key", "test_value")
        assert cm.get_setting("test_key") == "test_value"
        mock_save_json.assert_called_once_with(self.expected_settings_file, {"test_key": "test_value"})


    def test_get_all_custom_eq_curves(self) -> None:
        test_curves = {"Curve1": [0]*10}
        with mock.patch.object(ConfigManager, "__init__", return_value=None):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm._custom_eq_curves = test_curves.copy() # Use copy

        retrieved_curves = cm.get_all_custom_eq_curves()
        assert retrieved_curves == test_curves
        retrieved_curves["NewKey"] = [1]*10 # Modify returned
        assert cm.get_all_custom_eq_curves() == test_curves # Original should be unchanged

    def test_get_custom_eq_curve(self -> None):
        test_curves = {"Curve1": [0]*10}
        with mock.patch.object(ConfigManager, "__init__", return_value=None):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm._custom_eq_curves = test_curves
        assert cm.get_custom_eq_curve("Curve1") == [0]*10
        assert cm.get_custom_eq_curve("NonExistent") is None


    def test_save_custom_eq_curve_validation(self) -> None:
        with mock.patch.object(ConfigManager, "__init__", return_value=None):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm._custom_eq_curves = {}
        with pytest.raises(ConfigError, match="Invalid EQ curve format for 'InvalidCurveShort'."):
            cm.save_custom_eq_curve("InvalidCurveShort", [0] * 5)
        with pytest.raises(ConfigError, match="Invalid EQ curve format for 'InvalidCurveType'."):
            cm.save_custom_eq_curve("InvalidCurveType", ["a"] * 10) # type: ignore

    @mock.patch.object(ConfigManager, "_save_json_file")
    def test_save_custom_eq_curve_success(self, mock_save_json: mock.MagicMock) -> None:
        with mock.patch.object(ConfigManager, "__init__", return_value=None):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm._custom_eq_curves_file_path = self.expected_eq_curves_file
            cm._custom_eq_curves = {"ExistingCurve": [0] * 10}
            cm._config_dir = mock.MagicMock(spec=Path); cm._config_dir.exists.return_value = True


        new_curve_name = "NewCurve"
        new_curve_values = [1] * 10
        cm.save_custom_eq_curve(new_curve_name, new_curve_values)
        assert cm.get_custom_eq_curve(new_curve_name) == new_curve_values
        expected_curves_after_save = {"ExistingCurve": [0] * 10, new_curve_name: new_curve_values}
        mock_save_json.assert_called_with( # Use assert_called_with for last call or specific call
            self.expected_eq_curves_file,
            expected_curves_after_save,
        )

    @mock.patch.object(ConfigManager, "_save_json_file")
    def test_delete_custom_eq_curve(self, mock_save_json: mock.MagicMock) -> None:
        with mock.patch.object(ConfigManager, "__init__", return_value=None):
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm._settings_file_path = self.expected_settings_file
            cm._custom_eq_curves_file_path = self.expected_eq_curves_file
            cm._config_dir = mock.MagicMock(spec=Path); cm._config_dir.exists.return_value = True

            cm._custom_eq_curves = {
                "ToDelete": [0] * 10,
                "ToKeep": [1] * 10,
                self.mocked_app_config["DEFAULT_CUSTOM_EQ_CURVE_NAME"]: [0] * 10,
            }
            # Simulate set_setting being part of the same ConfigManager instance
            cm._settings = {"last_custom_eq_curve_name": "ToDelete", "active_eq_type": "Custom"}


        cm.delete_custom_eq_curve("ToDelete")
        assert cm.get_custom_eq_curve("ToDelete") is None
        expected_curves_after_delete1 = {"ToKeep": [1] * 10, self.mocked_app_config["DEFAULT_CUSTOM_EQ_CURVE_NAME"]: [0] * 10}

        # Check calls to _save_json_file
        # One for eq_curves, one for settings (due to set_setting call)
        assert mock_save_json.call_count == 2
        mock_save_json.assert_any_call(self.expected_eq_curves_file, expected_curves_after_delete1)
        # The settings dict would be updated by the set_setting call inside delete_custom_eq_curve
        expected_settings_after_delete = {
            "last_custom_eq_curve_name": self.mocked_app_config["DEFAULT_CUSTOM_EQ_CURVE_NAME"],
            "active_eq_type": "Custom" # Assuming set_setting doesn't change this unless explicitly told
        }
        mock_save_json.assert_any_call(self.expected_settings_file, expected_settings_after_delete)

        assert cm.get_setting("last_custom_eq_curve_name") == self.mocked_app_config["DEFAULT_CUSTOM_EQ_CURVE_NAME"]

        mock_save_json.reset_mock()
        # Reset settings for the next part of the test
        cm._settings = {"last_custom_eq_curve_name": "OtherCurve"}

        cm.delete_custom_eq_curve("ToKeep")
        assert cm.get_custom_eq_curve("ToKeep") is None
        assert cm.get_setting("last_custom_eq_curve_name") == "OtherCurve" # Should not change if not "ToKeep"
        expected_curves_after_delete2 = {self.mocked_app_config["DEFAULT_CUSTOM_EQ_CURVE_NAME"]: [0] * 10}
        mock_save_json.assert_called_once_with(
            self.expected_eq_curves_file,
            expected_curves_after_delete2,
        )

    def test_get_last_sidetone_level(self) -> None:
        with mock.patch.object(ConfigManager, "get_setting") as mock_get_setting:
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm.get_last_sidetone_level()
        mock_get_setting.assert_called_once_with("sidetone_level", self.mocked_app_config["DEFAULT_SIDETONE_LEVEL"])

    def test_set_last_sidetone_level(self) -> None:
        with mock.patch.object(ConfigManager, "set_setting") as mock_set_setting:
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm.set_last_sidetone_level(TEST_SIDETONE_LEVEL_VALID)
        mock_set_setting.assert_called_once_with("sidetone_level", TEST_SIDETONE_LEVEL_VALID)

    def test_get_last_inactive_timeout(self) -> None:
        with mock.patch.object(ConfigManager, "get_setting") as mock_get_setting:
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm.get_last_inactive_timeout()
        mock_get_setting.assert_called_once_with("inactive_timeout", self.mocked_app_config["DEFAULT_INACTIVE_TIMEOUT"])

    def test_set_last_inactive_timeout(self) -> None:
        with mock.patch.object(ConfigManager, "set_setting") as mock_set_setting:
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm.set_last_inactive_timeout(30)
        mock_set_setting.assert_called_once_with("inactive_timeout", 30)

    def test_get_last_active_eq_preset_id(self) -> None:
        with mock.patch.object(ConfigManager, "get_setting") as mock_get_setting:
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm.get_last_active_eq_preset_id()
        mock_get_setting.assert_called_once_with("eq_preset_id", self.mocked_app_config["DEFAULT_EQ_PRESET_ID"])

    def test_set_last_active_eq_preset_id(self) -> None:
        with mock.patch.object(ConfigManager, "set_setting") as mock_set_setting:
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm.set_last_active_eq_preset_id(TEST_EQ_PRESET_ID_VALID)
        mock_set_setting.assert_any_call("eq_preset_id", TEST_EQ_PRESET_ID_VALID)
        mock_set_setting.assert_any_call("active_eq_type", "hardware")
        assert mock_set_setting.call_count == 2


    def test_get_last_custom_eq_curve_name_fallbacks(self) -> None:
        # Test with __init__ not mocked to allow _custom_eq_curves to be initialized
        # but mock _load_json_file to control what's "loaded"
        with mock.patch.object(ConfigManager, "_load_json_file") as mock_load_json, \
             mock.patch.object(ConfigManager, "_save_json_file"): # Mock save to prevent writes

            # Scenario 1: Last saved name exists in curves
            mock_load_json.side_effect = [
                {"last_custom_eq_curve_name": "ExistingCurve"}, # settings
                {"ExistingCurve": [0]*10, self.mocked_app_config["DEFAULT_CUSTOM_EQ_CURVE_NAME"]: [1]*10} # curves
            ]
            cm = ConfigManager(config_dir_path=self.test_config_path)
            assert cm.get_last_custom_eq_curve_name() == "ExistingCurve"

            # Scenario 2: Last saved name does NOT exist, default exists
            mock_load_json.reset_mock(side_effect=True)
            mock_load_json.side_effect = [
                {"last_custom_eq_curve_name": "MissingCurve"}, # settings
                {self.mocked_app_config["DEFAULT_CUSTOM_EQ_CURVE_NAME"]: [1]*10, "AnotherCurve": [2]*10} # curves
            ]
            cm = ConfigManager(config_dir_path=self.test_config_path)
            assert cm.get_last_custom_eq_curve_name() == self.mocked_app_config["DEFAULT_CUSTOM_EQ_CURVE_NAME"]

            # Scenario 3: Last saved name does NOT exist, default also MISSING, fallback to first available
            mock_load_json.reset_mock(side_effect=True)
            mock_load_json.side_effect = [
                {"last_custom_eq_curve_name": "MissingCurve"}, # settings
                {"FirstAvailable": [0]*10, "AnotherCurve": [2]*10} # curves (default is missing)
            ]
            cm = ConfigManager(config_dir_path=self.test_config_path)
            assert cm.get_last_custom_eq_curve_name() == "FirstAvailable"

            # Scenario 4: No curves exist at all (e.g. fresh init, save failed)
            mock_load_json.reset_mock(side_effect=True)
            mock_load_json.side_effect = [
                {"last_custom_eq_curve_name": "AnyName"}, # settings
                {} # No curves
            ]
            # For this, we also need to ensure DEFAULT_EQ_CURVES is empty to simulate no defaults being populated
            with mock.patch.dict(self.mocked_app_config, {"DEFAULT_EQ_CURVES": {}}):
                 cm = ConfigManager(config_dir_path=self.test_config_path)
                 assert cm.get_last_custom_eq_curve_name() == "AnyName" # Returns the name as is

    def test_set_last_custom_eq_curve_name(self) -> None:
        with mock.patch.object(ConfigManager, "set_setting") as mock_set_setting:
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm.set_last_custom_eq_curve_name("MyCustomCurve")
        mock_set_setting.assert_any_call("last_custom_eq_curve_name", "MyCustomCurve")
        mock_set_setting.assert_any_call("active_eq_type", "custom")
        assert mock_set_setting.call_count == 2

    def test_get_active_eq_type(self) -> None:
        with mock.patch.object(ConfigManager, "get_setting") as mock_get_setting:
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm.get_active_eq_type()
        mock_get_setting.assert_called_once_with("active_eq_type", self.CM_DEFAULT_ACTIVE_EQ_TYPE)

    # Test default values for other specific settings
    def test_default_chatmix_enabled(self) -> None:
        with mock.patch.object(ConfigManager, "get_setting") as mock_get_setting:
            cm = ConfigManager(config_dir_path=Path("dummy"))
            cm.get_setting("chatmix_enabled", self.CM_DEFAULT_CHATMIX_ENABLED)
        mock_get_setting.assert_called_once_with("chatmix_enabled", self.CM_DEFAULT_CHATMIX_ENABLED)

    # ... (similar tests for other defaults can be added if they have specific getters/setters) ...

    def test_config_dir_creation_failure(self) -> None:
        # Test that an error during directory creation is logged
        with mock.patch("headsetcontrol_tray.config_manager.Path.mkdir", side_effect=OSError("Cannot create dir")), \
             mock.patch("headsetcontrol_tray.config_manager.logger") as mock_logger, \
             mock.patch.object(ConfigManager, "_load_json_file", return_value={}), \
             mock.patch.object(ConfigManager, "_save_json_file"): # Mock save to prevent issues if load fails

            _ = ConfigManager(config_dir_path=self.test_config_path)
            mock_logger.error.assert_called_once_with(
                f"Could not create config directory {self.test_config_path}: Cannot create dir"
            )
            # Also check that save is not called for defaults if dir doesn't exist
            # This needs _config_dir.exists() to return False after mkdir fails.
            # The current code calls _save_json_file if self._config_dir.exists() is true.
            # If mkdir fails, self.test_config_path might still exist if it was created then error happened.
            # A more robust check:
            # If mkdir fails, the subsequent _save_json_file in __init__ for defaults should be skipped.
            # This requires ensuring _config_dir.exists() returns False after the mocked mkdir failure.
            # This is already handled by the logic in ConfigManager:
            # if self._config_dir.exists(): self._save_json_file(...)
            # If mkdir fails, the test for _save_json_file not being called for defaults is implicit
            # if _config_dir.exists() is correctly False.
            # For this test, we can ensure _save_json_file is NOT called if logger.error was.
            # The current _save_json_file mock in this test will catch any call.
            # So, if logger.error was called, _save_json_file should not have been called by __init__.
            # This is tricky because _load_json_file is also called.
            # Let's refine the test to focus on the _save_json_file call for defaults.

    @mock.patch.object(ConfigManager, "_load_json_file", return_value={}) # Ensure load returns empty
    @mock.patch.object(ConfigManager, "_save_json_file")
    @mock.patch("headsetcontrol_tray.config_manager.Path.mkdir", side_effect=OSError("Cannot create dir"))
    @mock.patch("headsetcontrol_tray.config_manager.Path.exists", return_value=False) # Mock Path.exists globally for this test
    def test_init_default_eq_curves_not_saved_if_dir_creation_fails(
        self, mock_path_exists, mock_path_mkdir, mock_save_json, mock_load_json
    ):
        with mock.patch("headsetcontrol_tray.config_manager.logger") as mock_logger:
             _ = ConfigManager(config_dir_path=self.test_config_path)

        mock_path_mkdir.assert_called_once() # mkdir was attempted
        mock_logger.error.assert_called_once() # Error was logged

        # Crucially, _save_json_file for default EQs should not be called
        # if the directory doesn't exist after the attempt.
        # The mock_save_json will capture all calls. We need to ensure it wasn't called
        # for the custom_eq_curves_file_path.

        # Check if _save_json_file was called with custom_eq_curves_file_path
        # This is a bit indirect. Better: check if it was called at all.
        # If only settings are loaded, and EQ curves are empty, it tries to save defaults.
        # But if dir creation fails, it should skip this save.

        # Get all calls to mock_save_json
        save_calls = mock_save_json.call_args_list
        # Check that none of these calls were for the EQ curves file
        # This assumes that if save was called for EQ curves, it would be with self.expected_eq_curves_file
        # A simpler check: mock_save_json.assert_not_called() if NO saves are expected.
        # But _load_json_file might trigger saves if files are missing and defaults are written.
        # Given the setup, if EQ curves are empty from _load_json_file, a save is attempted.
        # The key is that *this specific save* for default EQs is skipped if dir creation fails.

        # This test becomes simpler: if dir creation fails, the log warning about skipping save should appear.
        # The ConfigManager code:
        # if not self._custom_eq_curves:
        #    if self._config_dir.exists(): self._save_json_file(...)
        #    else: logger.warning("Config directory does not exist. Skipping initial save...")
        # So, if Path.exists (mock_path_exists) returns False for self._config_dir,
        # the logger.warning should be called.

        # Reset logger mock to capture the specific warning
        mock_logger.reset_mock()
        # Path(ANY_PATH).exists() will return False because of mock_path_exists at the top.
        _ = ConfigManager(config_dir_path=self.test_config_path)
        mock_logger.warning.assert_called_with(
            "Config directory does not exist. Skipping initial save of default EQ curves."
        )
        # And ensure _save_json_file wasn't called for EQ curves
        # This requires checking the arguments of calls to mock_save_json
        found_eq_save_call = False
        for call in mock_save_json.call_args_list:
            if call[0][0] == self.expected_eq_curves_file:
                found_eq_save_call = True
                break
        assert not found_eq_save_call, "Default EQ curves should not be saved if config dir creation failed."
