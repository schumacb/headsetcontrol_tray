"""Tests for the macOS-specific OS layer implementation (`MacOSImpl`).

This module contains pytest tests for the `MacOSImpl` class, focusing on
macOS-specific behaviors such as directory path resolution and device setup flows
(though currently minimal for macOS). Mocks are used to simulate dependencies.
"""
from collections.abc import Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QMessageBox  # Import for use in test and for mock spec
import pytest

from headsetcontrol_tray.app_config import APP_NAME
from headsetcontrol_tray.os_layer.base import HIDManagerInterface
from headsetcontrol_tray.os_layer.macos import MacOSImpl


@pytest.fixture
def macos_impl_fixture() -> Iterator[MacOSImpl]:  # mocker removed
    """Fixture to create a MacOSImpl instance with a mocked HIDManager."""
    with patch(
        "headsetcontrol_tray.os_layer.macos.HIDConnectionManager",
        autospec=True,
    ) as mock_hid_manager_class:  # Patched HIDConnectionManager
        mock_hid_manager_instance = mock_hid_manager_class.return_value  # Use .return_value for autospec
        # spec=HIDConnectionManager is implicitly handled by autospec=True
        impl = MacOSImpl()
        impl._hid_manager = mock_hid_manager_instance  # noqa: SLF001 # Assigning mock for test purposes
        yield impl  # Use yield for pytest fixtures


def test_macos_impl_get_os_name(macos_impl_fixture: MacOSImpl) -> None:
    """Tests that get_os_name() returns 'macos'."""
    assert macos_impl_fixture.get_os_name() == "macos"


def test_macos_impl_get_hid_manager(macos_impl_fixture: MacOSImpl) -> None:  # mocker removed
    """Tests that get_hid_manager() returns a valid HIDManagerInterface instance."""
    hid_manager = macos_impl_fixture.get_hid_manager()
    # Check for a known attribute instead of exact MagicMock type due to autospec
    assert hasattr(hid_manager, "connect_device")
    assert isinstance(
        macos_impl_fixture._hid_manager, HIDManagerInterface,  # noqa: SLF001 # Accessing mock for assertion
    )


def test_macos_impl_get_config_dir(macos_impl_fixture: MacOSImpl) -> None:
    """Tests get_config_dir() for macOS standard path."""
    expected_path = Path.home() / "Library" / "Application Support" / APP_NAME.replace(" ", "")
    assert macos_impl_fixture.get_config_dir() == expected_path


def test_macos_impl_needs_device_setup(macos_impl_fixture: MacOSImpl) -> None:
    """Tests needs_device_setup() for macOS, expecting False."""
    assert macos_impl_fixture.needs_device_setup() is False


def test_macos_impl_perform_device_setup(macos_impl_fixture: MacOSImpl) -> None:  # mocker removed
    """Tests perform_device_setup() for macOS, expecting it to show an info dialog."""
    # Patch QMessageBox where it's looked up (PySide6.QtWidgets)
    # Provide spec for more robust mocking if QMessageBox methods are called on the class itself.
    with patch("PySide6.QtWidgets.QMessageBox", MagicMock(spec=QMessageBox)) as mock_qmessagebox_constructor:
        _mock_dialog_instance = mock_qmessagebox_constructor.return_value  # F841: Unused, constructor mock is asserted
        mock_parent_widget = MagicMock()

        success, proc_result, error = macos_impl_fixture.perform_device_setup(ui_parent=mock_parent_widget)

        assert success is False
        assert proc_result is None
        assert error is None
        # The code calls QMessageBox.information(ui_parent, ...), which is a static method.
        # So, the assertion should be on the mock_qmessagebox_constructor itself.
        mock_qmessagebox_constructor.information.assert_called_once()
