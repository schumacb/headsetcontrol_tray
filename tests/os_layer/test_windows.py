import os
from pathlib import Path
from unittest.mock import MagicMock, patch # Ensure patch is imported

import pytest

from headsetcontrol_tray.os_layer.windows import WindowsImpl # Removed WindowsHIDManager
from headsetcontrol_tray.os_layer.base import HIDManagerInterface
from headsetcontrol_tray.app_config import APP_NAME
# Import HIDConnectionManager for mocking
from headsetcontrol_tray.hid_manager import HIDConnectionManager


@pytest.fixture
def windows_impl_fixture(): # mocker removed
    with patch("headsetcontrol_tray.os_layer.windows.HIDConnectionManager") as mock_hid_manager_class: # Patched HIDConnectionManager
        mock_hid_manager_instance = MagicMock(spec=HIDConnectionManager) # Mock HIDConnectionManager
        mock_hid_manager_class.return_value = mock_hid_manager_instance
        impl = WindowsImpl()
        impl._hid_manager = mock_hid_manager_instance # Assign the correct mock
        yield impl # Use yield for pytest fixtures

def test_windows_impl_get_os_name(windows_impl_fixture):
    assert windows_impl_fixture.get_os_name() == "windows"

def test_windows_impl_get_hid_manager(windows_impl_fixture): # mocker removed
    assert isinstance(windows_impl_fixture.get_hid_manager(), MagicMock)
    assert isinstance(windows_impl_fixture._hid_manager, HIDManagerInterface)


@pytest.mark.parametrize(
    "appdata_val, expected_parent_name_segment, expected_app_name_folder",
    [
        ("C:\\Users\\TestUser\\AppData\\Roaming", "Roaming", APP_NAME.replace(" ", "")),
        (None, ".config", APP_NAME.lower().replace(" ", "_")),
    ],
)
def test_windows_impl_get_config_dir(windows_impl_fixture, appdata_val, expected_parent_name_segment, expected_app_name_folder):
    env_vars = {}
    if appdata_val:
        env_vars["APPDATA"] = appdata_val

    with patch.dict(os.environ, env_vars, clear=True):
        config_dir = windows_impl_fixture.get_config_dir()
        assert config_dir.name == expected_app_name_folder
        if appdata_val:
                assert config_dir.parent == Path(appdata_val) # Changed assertion
        else: # Fallback
            assert config_dir.parent == Path.home() / ".config"


@pytest.mark.parametrize(
    "local_appdata_val, expected_parent_name_segment, expected_app_name_folder",
    [
        ("C:\\Users\\TestUser\\AppData\\Local", "Local", APP_NAME.replace(" ", "")),
        (None, Path.home() / ".local" / "share", APP_NAME.lower().replace(" ", "_")),
    ]
)
def test_windows_impl_get_data_dir(windows_impl_fixture, local_appdata_val, expected_parent_name_segment, expected_app_name_folder):
    env_vars = {}
    if local_appdata_val:
        env_vars["LOCALAPPDATA"] = local_appdata_val

    with patch.dict(os.environ, env_vars, clear=True):
        data_dir = windows_impl_fixture.get_data_dir()
        assert data_dir.name == expected_app_name_folder
        if local_appdata_val:
                assert data_dir.parent == Path(local_appdata_val) # Changed assertion
        else: # Fallback
             assert data_dir.parent == Path.home() / ".local" / "share"


def test_windows_impl_needs_device_setup(windows_impl_fixture):
    assert windows_impl_fixture.needs_device_setup() is False

def test_windows_impl_perform_device_setup(windows_impl_fixture): # mocker removed
    with patch("headsetcontrol_tray.os_layer.windows.QMessageBox") as mock_qmessagebox:
        mock_parent_widget = MagicMock()

        success, proc_result, error = windows_impl_fixture.perform_device_setup(ui_parent=mock_parent_widget)

        assert success is False
        assert proc_result is None
        assert error is None
        mock_qmessagebox.information.assert_called_once()
