import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from headsetcontrol_tray.os_layer.windows import WindowsImpl, WindowsHIDManager
from headsetcontrol_tray.os_layer.base import HIDManagerInterface
from headsetcontrol_tray.app_config import APP_NAME


@pytest.fixture
def windows_impl_fixture(mocker): # Renamed
    mock_hid_manager = MagicMock(spec=WindowsHIDManager)
    mocker.patch("headsetcontrol_tray.os_layer.windows.WindowsHIDManager", return_value=mock_hid_manager)
    impl = WindowsImpl()
    impl._hid_manager = mock_hid_manager
    return impl

def test_windows_impl_get_os_name(windows_impl_fixture):
    assert windows_impl_fixture.get_os_name() == "windows"

def test_windows_impl_get_hid_manager(windows_impl_fixture, mocker):
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
            assert config_dir.parent.name == expected_parent_name_segment
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
            assert data_dir.parent.name == expected_parent_name_segment
        else: # Fallback
             assert data_dir.parent == Path.home() / ".local" / "share"


def test_windows_impl_needs_device_setup(windows_impl_fixture):
    assert windows_impl_fixture.needs_device_setup() is False

def test_windows_impl_perform_device_setup(windows_impl_fixture, mocker):
    # Patch QMessageBox from the correct module if it's different from PySide6.QtWidgets
    mock_qmessagebox = mocker.patch("headsetcontrol_tray.os_layer.windows.QMessageBox")
    mock_parent_widget = MagicMock()

    success, proc_result, error = windows_impl_fixture.perform_device_setup(ui_parent=mock_parent_widget)

    assert success is False
    assert proc_result is None
    assert error is None
    mock_qmessagebox.information.assert_called_once()
