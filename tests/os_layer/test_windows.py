import os
from pathlib import Path
from unittest.mock import MagicMock, patch # Ensure patch is imported

import pytest

from PySide6.QtWidgets import QMessageBox # Import for use in test and for mock spec
from headsetcontrol_tray.os_layer.windows import WindowsImpl
from headsetcontrol_tray.hid_manager import HIDConnectionManager # Keep for spec if needed
from headsetcontrol_tray.os_layer.base import HIDManagerInterface
from headsetcontrol_tray.app_config import APP_NAME


@pytest.fixture
def windows_impl_fixture(): # mocker removed
    with patch("headsetcontrol_tray.os_layer.windows.HIDConnectionManager", autospec=True) as mock_hid_manager_class: # Patched HIDConnectionManager
        mock_hid_manager_instance = mock_hid_manager_class.return_value # Use .return_value for autospec
        # spec=HIDConnectionManager is implicitly handled by autospec=True
        impl = WindowsImpl()
        impl._hid_manager = mock_hid_manager_instance # Assign the correct mock
        yield impl # Use yield for pytest fixtures

def test_windows_impl_get_os_name(windows_impl_fixture):
    assert windows_impl_fixture.get_os_name() == "windows"

def test_windows_impl_get_hid_manager(windows_impl_fixture): # mocker removed
    hid_manager = windows_impl_fixture.get_hid_manager()
    # Check for a known attribute instead of exact MagicMock type due to autospec
    assert hasattr(hid_manager, "connect_device")
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
            assert config_dir.parent == Path(appdata_val) # Check full parent path
        else: # Fallback
            assert config_dir.parent == Path.home() / ".config"


def test_windows_impl_needs_device_setup(windows_impl_fixture):
    assert windows_impl_fixture.needs_device_setup() is False

def test_windows_impl_perform_device_setup(windows_impl_fixture): # mocker removed
    # Patch QMessageBox where it's looked up (PySide6.QtWidgets)
    with patch("PySide6.QtWidgets.QMessageBox", MagicMock(spec=QMessageBox)) as mock_qmessagebox_constructor:
        mock_dialog_instance = mock_qmessagebox_constructor.return_value
        mock_parent_widget = MagicMock()

        success, proc_result, error = windows_impl_fixture.perform_device_setup(ui_parent=mock_parent_widget)

        assert success is False
        assert proc_result is None
        assert error is None
        # The code calls QMessageBox.information(ui_parent, ...), which is a static method.
        mock_qmessagebox_constructor.information.assert_called_once()
