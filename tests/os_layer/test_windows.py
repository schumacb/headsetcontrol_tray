import os
from pathlib import Path
from unittest.mock import MagicMock, patch  # Ensure patch is imported

import pytest

from headsetcontrol_tray.app_config import APP_NAME

# Import HIDConnectionManager for mocking - REMOVED
# from headsetcontrol_tray.hid_manager import HIDConnectionManager
from headsetcontrol_tray.os_layer.base import HIDManagerInterface
from headsetcontrol_tray.os_layer.windows import WindowsImpl  # Removed WindowsHIDManager


@pytest.fixture
def windows_impl_fixture():  # mocker removed
    with patch(
        "headsetcontrol_tray.os_layer.windows.HIDConnectionManager", autospec=True,  # Reverted to target name in module
    ) as mock_hid_manager_class:
        mock_hid_manager_instance = mock_hid_manager_class.return_value
        impl = WindowsImpl()
        impl._hid_manager = mock_hid_manager_instance
        yield impl  # Use yield for pytest fixtures


def test_windows_impl_get_os_name(windows_impl_fixture):
    assert windows_impl_fixture.get_os_name() == "windows"


def test_windows_impl_get_hid_manager(windows_impl_fixture):  # mocker removed
    # Check for a known attribute instead of exact MagicMock type due to autospec
    assert hasattr(windows_impl_fixture.get_hid_manager(), "connect_device")
    assert isinstance(windows_impl_fixture._hid_manager, HIDManagerInterface)


@pytest.mark.parametrize(
    "appdata_val, expected_app_name_folder",  # Removed expected_parent_name_segment
    [
        ("C:\\Users\\TestUser\\AppData\\Roaming", APP_NAME.replace(" ", "")),
        (None, APP_NAME.lower().replace(" ", "_")),  # Fallback case
    ],
)
def test_windows_impl_get_config_dir(
    windows_impl_fixture, appdata_val, expected_app_name_folder,  # Removed expected_parent_name_segment
):
    env_vars = {}
    if appdata_val:
        env_vars["APPDATA"] = appdata_val

    with patch.dict(os.environ, env_vars, clear=True):
        config_dir = windows_impl_fixture.get_config_dir()
        assert config_dir.name == expected_app_name_folder
        if appdata_val:
            assert config_dir.parent == Path(appdata_val)  # Changed assertion
        else:  # Fallback
            assert config_dir.parent == Path.home() / ".config"


@pytest.mark.parametrize(
    "local_appdata_val, expected_app_name_folder",  # Removed expected_parent_name_segment
    [
        ("C:\\Users\\TestUser\\AppData\\Local", APP_NAME.replace(" ", "")),
        (None, APP_NAME.lower().replace(" ", "_")),  # Fallback case
    ],
)
def test_windows_impl_get_data_dir(
    windows_impl_fixture, local_appdata_val, expected_app_name_folder,  # Removed expected_parent_name_segment
):
    env_vars = {}
    if local_appdata_val:
        env_vars["LOCALAPPDATA"] = local_appdata_val

    with patch.dict(os.environ, env_vars, clear=True):
        data_dir = windows_impl_fixture.get_data_dir()
        assert data_dir.name == expected_app_name_folder
        if local_appdata_val:
            assert data_dir.parent == Path(local_appdata_val)  # Changed assertion
        else:  # Fallback
            assert data_dir.parent == Path.home() / ".local" / "share"


def test_windows_impl_needs_device_setup(windows_impl_fixture):
    assert windows_impl_fixture.needs_device_setup() is False


def test_windows_impl_perform_device_setup(windows_impl_fixture):  # mocker removed
    with patch("headsetcontrol_tray.os_layer.windows.QMessageBox") as mock_qmessagebox:
        mock_parent_widget = MagicMock()

        success, proc_result, error = windows_impl_fixture.perform_device_setup(ui_parent=mock_parent_widget)

        assert success is False
        assert proc_result is None
        assert error is None
        mock_qmessagebox.information.assert_called_once()
