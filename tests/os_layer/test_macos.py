from pathlib import Path
from unittest.mock import MagicMock, patch  # Ensure patch is imported

import pytest

from headsetcontrol_tray.app_config import APP_NAME

# Import HIDConnectionManager for mocking - REMOVED
# from headsetcontrol_tray.hid_manager import HIDConnectionManager
from headsetcontrol_tray.os_layer.base import HIDManagerInterface
from headsetcontrol_tray.os_layer.macos import MacOSImpl  # Removed MacOSHIDManager


@pytest.fixture
def macos_impl_fixture():  # mocker removed
    with patch(
        "headsetcontrol_tray.os_layer.macos.HIDConnectionManager", autospec=True  # Reverted to target name in module
    ) as mock_hid_manager_class:
        mock_hid_manager_instance = mock_hid_manager_class.return_value
        impl = MacOSImpl()
        impl._hid_manager = mock_hid_manager_instance
        yield impl  # Use yield for pytest fixtures


def test_macos_impl_get_os_name(macos_impl_fixture):
    assert macos_impl_fixture.get_os_name() == "macos"


def test_macos_impl_get_hid_manager(macos_impl_fixture):  # mocker removed
    # Check for a known attribute instead of exact MagicMock type due to autospec
    assert hasattr(macos_impl_fixture.get_hid_manager(), "connect_device")
    assert isinstance(macos_impl_fixture._hid_manager, HIDManagerInterface)


def test_macos_impl_get_config_dir(macos_impl_fixture):
    expected_path = Path.home() / "Library" / "Application Support" / APP_NAME.replace(" ", "")
    assert macos_impl_fixture.get_config_dir() == expected_path


def test_macos_impl_get_data_dir(macos_impl_fixture):
    expected_path = Path.home() / "Library" / "Application Support" / APP_NAME.replace(" ", "")
    assert macos_impl_fixture.get_data_dir() == expected_path


def test_macos_impl_needs_device_setup(macos_impl_fixture):
    assert macos_impl_fixture.needs_device_setup() is False


def test_macos_impl_perform_device_setup(macos_impl_fixture):  # mocker removed
    with patch("headsetcontrol_tray.os_layer.macos.QMessageBox") as mock_qmessagebox:
        mock_parent_widget = MagicMock()

        success, proc_result, error = macos_impl_fixture.perform_device_setup(ui_parent=mock_parent_widget)

        assert success is False
        assert proc_result is None
        assert error is None
        mock_qmessagebox.information.assert_called_once()
