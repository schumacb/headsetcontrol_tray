"""Tests for the Windows-specific OS layer implementation (`WindowsImpl`).

This module contains pytest tests for the `WindowsImpl` class, focusing on
Windows-specific behaviors such as directory path resolution using environment
variables (APPDATA) and device setup flows (currently minimal for Windows).
Mocks are used to simulate dependencies.
"""
from collections.abc import Iterator
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

from PySide6.QtWidgets import QMessageBox  # Import for use in test and for mock spec
import pytest

from headsetcontrol_tray.app_config import APP_NAME
from headsetcontrol_tray.os_layer.base import HIDManagerInterface
from headsetcontrol_tray.os_layer.windows import WindowsImpl


@pytest.fixture
def windows_impl_fixture() -> Iterator[WindowsImpl]:  # mocker removed
    """Fixture to create a WindowsImpl instance with a mocked HIDManager."""
    with patch(
        "headsetcontrol_tray.os_layer.windows.HIDConnectionManager",
        autospec=True,
    ) as mock_hid_manager_class:  # Patched HIDConnectionManager
        mock_hid_manager_instance = mock_hid_manager_class.return_value  # Use .return_value for autospec
        # spec=HIDConnectionManager is implicitly handled by autospec=True
        impl = WindowsImpl()
        impl._hid_manager = mock_hid_manager_instance  # noqa: SLF001 # Assigning mock for test purposes
        yield impl  # Use yield for pytest fixtures


def test_windows_impl_get_os_name(windows_impl_fixture: WindowsImpl) -> None:
    """Tests that get_os_name() returns 'windows'."""
    assert windows_impl_fixture.get_os_name() == "windows"


def test_windows_impl_get_hid_manager(windows_impl_fixture: WindowsImpl) -> None:  # mocker removed
    """Tests that get_hid_manager() returns a valid HIDManagerInterface instance."""
    hid_manager = windows_impl_fixture.get_hid_manager()
    # Check for a known attribute instead of exact MagicMock type due to autospec
    assert hasattr(hid_manager, "connect_device")
    assert isinstance(
        windows_impl_fixture._hid_manager, HIDManagerInterface,  # noqa: SLF001 # Accessing mock for assertion
    )


@pytest.mark.parametrize(
    ("appdata_val", "expected_app_name_folder"),  # Removed expected_parent_name_segment
    [
        ("C:\\Users\\TestUser\\AppData\\Roaming", APP_NAME.replace(" ", "")),
        (None, APP_NAME.lower().replace(" ", "_")),
    ],
)
def test_windows_impl_get_config_dir(
    windows_impl_fixture: WindowsImpl,
    appdata_val: str | None,
    expected_app_name_folder: str,
) -> None:
    """Tests get_config_dir() for Windows with and without APPDATA environment variable."""
    env_vars = {}
    if appdata_val:
        env_vars["APPDATA"] = appdata_val

    with patch.dict(os.environ, env_vars, clear=True):
        config_dir = windows_impl_fixture.get_config_dir()
        assert config_dir.name == expected_app_name_folder
        if appdata_val:
            assert config_dir.parent == Path(appdata_val)  # Check full parent path
        else:  # Fallback
            assert config_dir.parent == Path.home() / ".config"


def test_windows_impl_needs_device_setup(windows_impl_fixture: WindowsImpl) -> None:
    """Tests needs_device_setup() for Windows, expecting False."""
    assert windows_impl_fixture.needs_device_setup() is False


def test_windows_impl_perform_device_setup(windows_impl_fixture: WindowsImpl) -> None:  # mocker removed
    """Tests perform_device_setup() for Windows, expecting it to show an info dialog."""
    # Patch QMessageBox where it's looked up (PySide6.QtWidgets)
    with patch("PySide6.QtWidgets.QMessageBox", MagicMock(spec=QMessageBox)) as mock_qmessagebox_constructor:
        _mock_dialog_instance = mock_qmessagebox_constructor.return_value # F841: Unused
        mock_parent_widget = MagicMock()

        success, proc_result, error = windows_impl_fixture.perform_device_setup(ui_parent=mock_parent_widget)

        assert success is False
        assert proc_result is None
        assert error is None
        # The code calls QMessageBox.information(ui_parent, ...), which is a static method.
        mock_qmessagebox_constructor.information.assert_called_once()
