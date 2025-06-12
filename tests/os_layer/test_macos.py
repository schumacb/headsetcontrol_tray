from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from headsetcontrol_tray.os_layer.macos import MacOSImpl, MacOSHIDManager
from headsetcontrol_tray.os_layer.base import HIDManagerInterface
from headsetcontrol_tray.app_config import APP_NAME


@pytest.fixture
def macos_impl_fixture(mocker): # Renamed
    mock_hid_manager = MagicMock(spec=MacOSHIDManager)
    mocker.patch("headsetcontrol_tray.os_layer.macos.MacOSHIDManager", return_value=mock_hid_manager)
    impl = MacOSImpl()
    impl._hid_manager = mock_hid_manager
    return impl

def test_macos_impl_get_os_name(macos_impl_fixture):
    assert macos_impl_fixture.get_os_name() == "macos"

def test_macos_impl_get_hid_manager(macos_impl_fixture, mocker):
    assert isinstance(macos_impl_fixture.get_hid_manager(), MagicMock)
    assert isinstance(macos_impl_fixture._hid_manager, HIDManagerInterface)

def test_macos_impl_get_config_dir(macos_impl_fixture):
    expected_path = Path.home() / "Library" / "Application Support" / APP_NAME.replace(" ", "")
    assert macos_impl_fixture.get_config_dir() == expected_path

def test_macos_impl_get_data_dir(macos_impl_fixture):
    expected_path = Path.home() / "Library" / "Application Support" / APP_NAME.replace(" ", "")
    assert macos_impl_fixture.get_data_dir() == expected_path

def test_macos_impl_needs_device_setup(macos_impl_fixture):
    assert macos_impl_fixture.needs_device_setup() is False

def test_macos_impl_perform_device_setup(macos_impl_fixture, mocker):
    mock_qmessagebox = mocker.patch("headsetcontrol_tray.os_layer.macos.QMessageBox")
    mock_parent_widget = MagicMock()

    success, proc_result, error = macos_impl_fixture.perform_device_setup(ui_parent=mock_parent_widget)

    assert success is False
    assert proc_result is None
    assert error is None
    mock_qmessagebox.information.assert_called_once()
