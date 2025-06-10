import json
import logging
from pathlib import Path
import unittest
from unittest import mock

# Assuming app_config and ConfigManager are in src/headsetcontrol_tray
from headsetcontrol_tray import app_config
from headsetcontrol_tray.config_manager import ConfigManager

# Disable logging for tests to keep output clean, unless specifically testing logging
logging.disable(logging.CRITICAL)


class TestConfigManager(unittest.TestCase):
    def setUp(self):
        self.mock_config_dir = mock.MagicMock(spec=Path)
        self.mock_config_file = self.mock_config_dir / "settings.json"
        self.mock_eq_curves_file = self.mock_config_dir / "custom_eq_curves.json"

        # Patch only existing constants in app_config
        self.app_config_patcher = mock.patch.multiple(
            app_config,
            CONFIG_DIR=self.mock_config_dir,
            CONFIG_FILE=self.mock_config_file,
            CUSTOM_EQ_CURVES_FILE=self.mock_eq_curves_file,
            DEFAULT_EQ_CURVES={"DefaultFlat": [0] * 10},
            DEFAULT_CUSTOM_EQ_CURVE_NAME="DefaultFlat",  # Used by ConfigManager
            DEFAULT_SIDETONE_LEVEL=64,  # Used by ConfigManager
            DEFAULT_EQ_PRESET_ID=0,  # Used by ConfigManager
            DEFAULT_INACTIVE_TIMEOUT=15,  # Used by ConfigManager
        )
        self.app_config_patcher.start()

        # Manually define hardcoded defaults used in ConfigManager if not from app_config,
        # for assertion purposes in tests. These are NOT patching app_config.
        self.CM_DEFAULT_ACTIVE_EQ_TYPE = "custom"
        self.CM_DEFAULT_CHATMIX_ENABLED = True
        self.CM_DEFAULT_AUTO_MUTE_MIC_ENABLED = False
        self.CM_DEFAULT_RUN_ON_STARTUP_ENABLED = True
        self.CM_DEFAULT_MINIMIZE_TO_TRAY_ENABLED = True
        self.CM_DEFAULT_CHECK_FOR_UPDATES_ENABLED = True
        self.CM_DEFAULT_INCLUDE_PRERELEASES_ENABLED = False
        self.CM_DEFAULT_DARK_MODE = "auto"

    def tearDown(self):
        self.app_config_patcher.stop()

    @mock.patch.object(ConfigManager, "_load_json_file")
    @mock.patch.object(ConfigManager, "_save_json_file")
    def test_init_paths_created_and_loaded(self, mock_save_json, mock_load_json):
        mock_load_json.side_effect = [{"some_setting": "value"}, {"MyCurve": [1] * 10}]
        cm = ConfigManager()
        self.mock_config_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        self.assertEqual(mock_load_json.call_count, 2)
        mock_load_json.assert_any_call(self.mock_config_file)
        mock_load_json.assert_any_call(self.mock_eq_curves_file)
        self.assertEqual(cm._settings, {"some_setting": "value"})
        self.assertEqual(cm._custom_eq_curves, {"MyCurve": [1] * 10})
        mock_save_json.assert_not_called()

    @mock.patch.object(ConfigManager, "_load_json_file")
    @mock.patch.object(ConfigManager, "_save_json_file")
    def test_init_default_eq_curves_saved_if_empty(
        self,
        mock_save_json,
        mock_load_json,
    ):
        mock_load_json.side_effect = [{"some_setting": "value"}, {}]
        cm = ConfigManager()
        self.mock_config_dir.mkdir.assert_called_once_with(parents=True, exist_ok=True)
        self.assertEqual(mock_load_json.call_count, 2)
        self.assertEqual(cm._custom_eq_curves, app_config.DEFAULT_EQ_CURVES)
        mock_save_json.assert_called_once_with(
            self.mock_eq_curves_file,
            app_config.DEFAULT_EQ_CURVES,
        )

    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch("json.load")
    def test_load_json_file_success(self, mock_json_load, mock_open_file):
        mock_file_path = mock.MagicMock(spec=Path)
        mock_file_path.exists.return_value = True
        expected_data = {"key": "value"}
        mock_json_load.return_value = expected_data
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._settings = {}
            cm._custom_eq_curves = {}
            loaded_data = cm._load_json_file(mock_file_path)
        mock_file_path.exists.assert_called_once()
        mock_open_file.assert_called_once_with(mock_file_path)
        mock_json_load.assert_called_once()
        self.assertEqual(loaded_data, expected_data)

    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch("json.load", side_effect=json.JSONDecodeError("Error", "doc", 0))
    def test_load_json_file_decode_error(self, mock_json_load_raises, mock_open_file):
        mock_file_path = mock.MagicMock(spec=Path)
        mock_file_path.exists.return_value = True
        with (
            mock.patch.object(ConfigManager, "__init__", lambda x: None),
            mock.patch("headsetcontrol_tray.config_manager.logger") as mock_logger,
        ):
            cm = ConfigManager()
            cm._settings = {}
            cm._custom_eq_curves = {}
            loaded_data = cm._load_json_file(mock_file_path)
        mock_logger.warning.assert_called_once()
        self.assertEqual(loaded_data, {})

    def test_load_json_file_does_not_exist(self):
        mock_file_path = mock.MagicMock(spec=Path)
        mock_file_path.exists.return_value = False
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._settings = {}
            cm._custom_eq_curves = {}
            loaded_data = cm._load_json_file(mock_file_path)
        self.assertEqual(loaded_data, {})

    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch("json.dump")
    def test_save_json_file_success(self, mock_json_dump, mock_open_file):
        mock_file_path = mock.MagicMock(spec=Path)
        data_to_save = {"key": "value"}
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._settings = {}
            cm._custom_eq_curves = {}
            cm._save_json_file(mock_file_path, data_to_save)
        mock_open_file.assert_called_once_with(mock_file_path, "w")
        mock_json_dump.assert_called_once_with(
            data_to_save,
            mock_open_file.return_value.__enter__.return_value,
            indent=4,
        )

    @mock.patch("builtins.open", side_effect=OSError("Disk full"))
    @mock.patch("json.dump")
    def test_save_json_file_io_error(
        self,
        mock_json_dump,
        mock_open_file_raises_ioerror,
    ):
        mock_file_path = mock.MagicMock(spec=Path)
        data_to_save = {"key": "value"}
        with (
            mock.patch.object(ConfigManager, "__init__", lambda x: None),
            mock.patch("headsetcontrol_tray.config_manager.logger") as mock_logger,
        ):
            cm = ConfigManager()
            cm._settings = {}
            cm._custom_eq_curves = {}
            cm._save_json_file(mock_file_path, data_to_save)
        mock_json_dump.assert_not_called()
        mock_logger.error.assert_called_once()

    @mock.patch("builtins.open", new_callable=mock.mock_open)
    @mock.patch("json.dump", side_effect=OSError("Permission denied"))
    def test_save_json_file_os_error_on_dump(
        self,
        mock_json_dump_raises_oserror,
        mock_open_file,
    ):
        mock_file_path = mock.MagicMock(spec=Path)
        data_to_save = {"key": "value"}
        with (
            mock.patch.object(ConfigManager, "__init__", lambda x: None),
            mock.patch("headsetcontrol_tray.config_manager.logger") as mock_logger,
        ):
            cm = ConfigManager()
            cm._settings = {}
            cm._custom_eq_curves = {}
            cm._save_json_file(mock_file_path, data_to_save)
        mock_logger.error.assert_called_once()

    def test_get_setting(self):
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._settings = {"existing_key": "existing_value"}
            cm._custom_eq_curves = {}
        self.assertEqual(cm.get_setting("existing_key"), "existing_value")
        self.assertIsNone(cm.get_setting("non_existing_key"))
        self.assertEqual(
            cm.get_setting("non_existing_key_with_default", "default_val"),
            "default_val",
        )

    @mock.patch.object(ConfigManager, "_save_json_file")
    def test_set_setting(self, mock_save_json):
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._settings = {}
            cm._custom_eq_curves = {}
        cm.set_setting("test_key", "test_value")
        self.assertEqual(cm._settings["test_key"], "test_value")
        mock_save_json.assert_called_once_with(self.mock_config_file, cm._settings)

    def test_get_all_custom_eq_curves(self):
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._custom_eq_curves = {"Curve1": [0] * 10, "Curve2": [1] * 10}
        self.assertEqual(
            cm.get_all_custom_eq_curves(),
            {"Curve1": [0] * 10, "Curve2": [1] * 10},
        )

    def test_get_custom_eq_curve(self):
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._custom_eq_curves = {"MyCurve": [1] * 10}
        self.assertEqual(cm.get_custom_eq_curve("MyCurve"), [1] * 10)
        self.assertIsNone(cm.get_custom_eq_curve("NonExistentCurve"))

    def test_save_custom_eq_curve_validation(self):
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._custom_eq_curves = {}
            cm._settings = {}
        with self.assertRaises(ValueError):
            cm.save_custom_eq_curve("InvalidCurveShort", [0] * 5)
        with self.assertRaises(ValueError):
            cm.save_custom_eq_curve("InvalidCurveLong", [0] * 11)
        with self.assertRaises(ValueError):
            cm.save_custom_eq_curve("InvalidCurveType", ["a"] * 10)  # type: ignore[list-item]
        with self.assertRaises(ValueError):
            cm.save_custom_eq_curve("NoValues", [])

    @mock.patch.object(ConfigManager, "_save_json_file")
    def test_save_custom_eq_curve_success(self, mock_save_json):
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._custom_eq_curves = {"ExistingCurve": [0] * 10}
            cm._settings = {}
        new_curve_name = "NewCurve"
        new_curve_values = [1] * 10
        cm.save_custom_eq_curve(new_curve_name, new_curve_values)
        self.assertIn(new_curve_name, cm._custom_eq_curves)
        mock_save_json.assert_called_with(
            self.mock_eq_curves_file,
            cm._custom_eq_curves,
        )
        # Note: save_custom_eq_curve itself doesn't call set_last_custom_eq_curve_name.
        # That's typically handled by UI logic after successful save.

    @mock.patch.object(ConfigManager, "_save_json_file")
    def test_delete_custom_eq_curve(self, mock_save_json):
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._custom_eq_curves = {
                "ToDelete": [0] * 10,
                "ToKeep": [1] * 10,
                app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME: [0] * 10,
            }
            cm._settings = {
                "last_custom_eq_curve_name": "ToDelete",
                "active_eq_type": "Custom",
            }

        cm.delete_custom_eq_curve("ToDelete")
        self.assertNotIn("ToDelete", cm._custom_eq_curves)
        mock_save_json.assert_any_call(self.mock_eq_curves_file, cm._custom_eq_curves)
        self.assertEqual(
            cm.get_setting("last_custom_eq_curve_name"),
            app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME,
        )

        mock_save_json.reset_mock()
        cm._settings = {"last_custom_eq_curve_name": "OtherCurve"}
        cm.delete_custom_eq_curve("ToKeep")  # Deleting a non-active, non-default curve
        self.assertNotIn("ToKeep", cm._custom_eq_curves)
        self.assertEqual(cm.get_setting("last_custom_eq_curve_name"), "OtherCurve")

        # Assertions for scenario 2, after reset_mock:
        # _save_json_file should have been called exactly once (for eq_curves_file)
        # and not for config_file if the deleted curve was not active.
        mock_save_json.assert_called_once_with(
            self.mock_eq_curves_file,
            cm._custom_eq_curves,
        )

    # Test specific setting shortcuts by checking their interaction with get_setting/set_setting
    def test_sidetone_level_shortcuts(self):
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._settings = {}
            cm._custom_eq_curves = {}
            with (
                mock.patch.object(cm, "get_setting") as mock_get,
                mock.patch.object(cm, "set_setting") as mock_set,
            ):
                mock_get.return_value = 50
                self.assertEqual(cm.get_last_sidetone_level(), 50)
                mock_get.assert_called_once_with(
                    "sidetone_level",
                    app_config.DEFAULT_SIDETONE_LEVEL,
                )
                cm.set_last_sidetone_level(75)
                mock_set.assert_called_once_with("sidetone_level", 75)

    def test_eq_preset_id_shortcuts(self):
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._settings = {}
            cm._custom_eq_curves = {}
            with (
                mock.patch.object(cm, "get_setting") as mock_get,
                mock.patch.object(cm, "set_setting") as mock_set,
            ):
                mock_get.return_value = 2
                self.assertEqual(cm.get_last_active_eq_preset_id(), 2)
                mock_get.assert_called_once_with(
                    "eq_preset_id",
                    app_config.DEFAULT_EQ_PRESET_ID,
                )
                cm.set_last_active_eq_preset_id(3)
                # set_last_active_eq_preset_id calls set_setting twice
                mock_set.assert_any_call("eq_preset_id", 3)
                mock_set.assert_any_call("active_eq_type", "hardware")

    def test_active_eq_type_shortcuts(self):
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._settings = {}
            cm._custom_eq_curves = {}
            with (
                mock.patch.object(cm, "get_setting") as mock_get,
                mock.patch.object(cm, "set_setting") as mock_set,
            ):
                mock_get.return_value = "Preset"
                self.assertEqual(cm.get_active_eq_type(), "Preset")
                mock_get.assert_called_once_with(
                    "active_eq_type",
                    self.CM_DEFAULT_ACTIVE_EQ_TYPE,
                )
                # Note: There is no direct set_active_eq_type in ConfigManager.
                # It's set by set_last_active_eq_preset_id or set_last_custom_eq_curve_name.

    def test_get_last_custom_eq_curve_name_fallbacks(self):
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._settings = {}
            cm._custom_eq_curves = {}

            cm._settings = {"last_custom_eq_curve_name": "MyFavCurve"}
            cm._custom_eq_curves = {
                "MyFavCurve": [1] * 10,
                app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME: [0] * 10,
            }
            self.assertEqual(cm.get_last_custom_eq_curve_name(), "MyFavCurve")

            cm._settings = {"last_custom_eq_curve_name": "NonExistent"}
            cm._custom_eq_curves = {
                app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME: [0] * 10,
                "AnotherCurve": [2] * 10,
            }
            self.assertEqual(
                cm.get_last_custom_eq_curve_name(),
                app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME,
            )

            cm._settings = {"last_custom_eq_curve_name": "NonExistent"}
            cm._custom_eq_curves = {"FirstCurve": [3] * 10, "SecondCurve": [4] * 10}
            # Ensure DEFAULT_CUSTOM_EQ_CURVE_NAME is not in this set for the test
            if app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME in cm._custom_eq_curves:
                del cm._custom_eq_curves[app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME]
            self.assertEqual(cm.get_last_custom_eq_curve_name(), "FirstCurve")

            cm._settings = {"last_custom_eq_curve_name": "NonExistentCurveOnly"}
            cm._custom_eq_curves = {}  # No curves at all
            self.assertEqual(cm.get_last_custom_eq_curve_name(), "NonExistentCurveOnly")

            cm._settings = {}  # No setting for last_custom_eq_curve_name
            cm._custom_eq_curves = {app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME: [0] * 10}
            self.assertEqual(
                cm.get_last_custom_eq_curve_name(),
                app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME,
            )

            cm._settings = {}
            cm._custom_eq_curves = {"FirstCurve": [3] * 10, "SecondCurve": [4] * 10}
            if app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME in cm._custom_eq_curves:
                del cm._custom_eq_curves[app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME]
            self.assertEqual(cm.get_last_custom_eq_curve_name(), "FirstCurve")

            cm._settings = {}
            cm._custom_eq_curves = {}
            self.assertEqual(
                cm.get_last_custom_eq_curve_name(),
                app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME,
            )

    def test_set_last_custom_eq_curve_name(self):
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._settings = {}
            cm._custom_eq_curves = {}
            with mock.patch.object(cm, "set_setting") as mock_set:
                cm.set_last_custom_eq_curve_name("MyNewCustomCurve")
                mock_set.assert_any_call(
                    "last_custom_eq_curve_name",
                    "MyNewCustomCurve",
                )
                mock_set.assert_any_call("active_eq_type", "custom")

    # The following tests verify get_setting with various hardcoded defaults from ConfigManager
    # if specific getters for them don't exist in ConfigManager itself.
    def test_get_setting_for_chatmix_enabled(self):
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._settings = {}
            self.assertEqual(
                cm.get_setting("chatmix_enabled", self.CM_DEFAULT_CHATMIX_ENABLED),
                True,
            )
            cm._settings = {"chatmix_enabled": False}
            self.assertEqual(
                cm.get_setting("chatmix_enabled", self.CM_DEFAULT_CHATMIX_ENABLED),
                False,
            )

    def test_get_setting_for_auto_mute_mic_enabled(self):
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._settings = {}
            self.assertEqual(
                cm.get_setting(
                    "auto_mute_mic_enabled",
                    self.CM_DEFAULT_AUTO_MUTE_MIC_ENABLED,
                ),
                False,
            )
            cm._settings = {"auto_mute_mic_enabled": True}
            self.assertEqual(
                cm.get_setting(
                    "auto_mute_mic_enabled",
                    self.CM_DEFAULT_AUTO_MUTE_MIC_ENABLED,
                ),
                True,
            )

    def test_get_setting_for_run_on_startup_enabled(self):
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._settings = {}
            self.assertEqual(
                cm.get_setting(
                    "run_on_startup_enabled",
                    self.CM_DEFAULT_RUN_ON_STARTUP_ENABLED,
                ),
                True,
            )
            cm._settings = {"run_on_startup_enabled": False}
            self.assertEqual(
                cm.get_setting(
                    "run_on_startup_enabled",
                    self.CM_DEFAULT_RUN_ON_STARTUP_ENABLED,
                ),
                False,
            )

    def test_get_setting_for_minimize_to_tray_enabled(self):
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._settings = {}
            self.assertEqual(
                cm.get_setting(
                    "minimize_to_tray_enabled",
                    self.CM_DEFAULT_MINIMIZE_TO_TRAY_ENABLED,
                ),
                True,
            )
            cm._settings = {"minimize_to_tray_enabled": False}
            self.assertEqual(
                cm.get_setting(
                    "minimize_to_tray_enabled",
                    self.CM_DEFAULT_MINIMIZE_TO_TRAY_ENABLED,
                ),
                False,
            )

    def test_get_setting_for_check_for_updates_enabled(self):
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._settings = {}
            self.assertEqual(
                cm.get_setting(
                    "check_for_updates_enabled",
                    self.CM_DEFAULT_CHECK_FOR_UPDATES_ENABLED,
                ),
                True,
            )
            cm._settings = {"check_for_updates_enabled": False}
            self.assertEqual(
                cm.get_setting(
                    "check_for_updates_enabled",
                    self.CM_DEFAULT_CHECK_FOR_UPDATES_ENABLED,
                ),
                False,
            )

    def test_get_setting_for_include_prereleases_enabled(self):
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._settings = {}
            self.assertEqual(
                cm.get_setting(
                    "include_prereleases_enabled",
                    self.CM_DEFAULT_INCLUDE_PRERELEASES_ENABLED,
                ),
                False,
            )
            cm._settings = {"include_prereleases_enabled": True}
            self.assertEqual(
                cm.get_setting(
                    "include_prereleases_enabled",
                    self.CM_DEFAULT_INCLUDE_PRERELEASES_ENABLED,
                ),
                True,
            )

    def test_get_setting_for_last_selected_device_serial(
        self,
    ):  # Covers get_last_selected_device_serial
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._settings = {}
            self.assertIsNone(cm.get_setting("last_selected_device_serial", None))
            cm._settings = {"last_selected_device_serial": "SERIAL123"}
            self.assertEqual(
                cm.get_setting("last_selected_device_serial", None),
                "SERIAL123",
            )

    def test_get_setting_for_dark_mode(self):  # Covers get_dark_mode
        with mock.patch.object(ConfigManager, "__init__", lambda x: None):
            cm = ConfigManager()
            cm._settings = {}
            self.assertEqual(
                cm.get_setting("dark_mode", self.CM_DEFAULT_DARK_MODE),
                "auto",
            )
            cm._settings = {"dark_mode": "dark"}
            self.assertEqual(
                cm.get_setting("dark_mode", self.CM_DEFAULT_DARK_MODE),
                "dark",
            )


if __name__ == "__main__":
    unittest.main()
