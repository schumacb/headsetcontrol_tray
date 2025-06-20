"""Tests for the Linux-specific OS layer implementation (`LinuxImpl`).

This module contains pytest tests for the `LinuxImpl` class, covering aspects
such as directory path resolution, device setup checks (udev rules), and the
execution flow of OS-specific setup processes like running helper scripts via pkexec.
Mocks are heavily used to isolate `LinuxImpl` from actual system interactions.
"""
from collections.abc import Iterator
import os
from pathlib import Path
import subprocess
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from headsetcontrol_tray.app_config import APP_NAME
from headsetcontrol_tray.exceptions import TrayAppInitializationError
from headsetcontrol_tray.os_layer.base import HIDManagerInterface
from headsetcontrol_tray.os_layer.linux import LinuxImpl

# Mock constants for pkexec exit codes (mirroring app.py or LinuxImpl)
PKEXEC_EXIT_SUCCESS = 0
PKEXEC_EXIT_USER_CANCELLED = 126
PKEXEC_EXIT_AUTH_FAILED = 127
PKEXEC_EXIT_OTHER_ERROR = 1  # Example for other script errors


@pytest.fixture
def linux_impl_fixture() -> Iterator[LinuxImpl]:  # mocker removed
    """Fixture to create a LinuxImpl instance with mocked UDEVManager and HIDManager."""
    with (
        patch("headsetcontrol_tray.os_layer.linux.UDEVManager", autospec=True) as mock_udev_manager_class,
        patch("headsetcontrol_tray.os_layer.linux.HIDConnectionManager", autospec=True) as mock_hid_manager_class,
    ):  # Patched HIDConnectionManager
        mock_udev_manager_instance = mock_udev_manager_class.return_value  # Use .return_value for autospec

        mock_hid_manager_instance = mock_hid_manager_class.return_value  # Use .return_value for autospec
        # spec=HIDConnectionManager is implicitly handled by autospec=True

        impl = LinuxImpl()
        # Store mocks directly on the instance for tests to access if needed
        impl._udev_manager = mock_udev_manager_instance  # noqa: SLF001 # Assigning mocks for test purposes
        impl._hid_manager = mock_hid_manager_instance  # noqa: SLF001 # Assigning mocks for test purposes
        yield impl  # Use yield for pytest fixtures


def test_linux_impl_get_os_name(linux_impl_fixture: LinuxImpl) -> None:
    """Tests that get_os_name() returns 'linux'."""
    assert linux_impl_fixture.get_os_name() == "linux"


def test_linux_impl_get_hid_manager(linux_impl_fixture: LinuxImpl) -> None:  # mocker removed
    """Tests that get_hid_manager() returns a valid HIDManagerInterface instance."""
    hid_manager = linux_impl_fixture.get_hid_manager()
    # Check for a known attribute instead of exact MagicMock type due to autospec
    assert hasattr(hid_manager, "connect_device")
    assert isinstance(
        linux_impl_fixture._hid_manager, HIDManagerInterface,  # noqa: SLF001 # Accessing mocked attribute for assertion
    )


@pytest.mark.parametrize(
    ("xdg_home", "expected_parent", "expected_name_part"),
    [
        ("/custom/config", Path("/custom/config"), APP_NAME.lower().replace(" ", "_")),
        (None, Path.home() / ".config", APP_NAME.lower().replace(" ", "_")),
    ],
)
def test_linux_impl_get_config_dir(
    linux_impl_fixture: LinuxImpl, xdg_home: str | None, expected_parent: Path, expected_name_part: str,
) -> None:
    """Tests get_config_dir() with and without XDG_CONFIG_HOME environment variable."""
    env_vars = {}
    if xdg_home:
        env_vars["XDG_CONFIG_HOME"] = xdg_home

    with patch.dict(os.environ, env_vars, clear=True):
        config_dir = linux_impl_fixture.get_config_dir()
        assert config_dir.name == expected_name_part
        assert config_dir.parent == expected_parent


def test_linux_impl_needs_device_setup_rules_not_installed(linux_impl_fixture: LinuxImpl) -> None:
    """Tests needs_device_setup() when udev rules are not installed."""
    linux_impl_fixture._udev_manager.are_rules_installed.return_value = False  # noqa: SLF001 # Accessing/configuring mock
    assert linux_impl_fixture.needs_device_setup() is True


def test_linux_impl_needs_device_setup_rules_installed(linux_impl_fixture: LinuxImpl) -> None:
    """Tests needs_device_setup() when udev rules are already installed."""
    linux_impl_fixture._udev_manager.are_rules_installed.return_value = True  # noqa: SLF001 # Accessing/configuring mock
    assert linux_impl_fixture.needs_device_setup() is False


# --- Tests for perform_device_setup ---


def test_linux_impl_perform_device_setup_prepare_fails(linux_impl_fixture: LinuxImpl) -> None:
    """Tests perform_device_setup() when udev rule preparation fails."""
    linux_impl_fixture._udev_manager.create_rules_interactive.return_value = False  # noqa: SLF001 # Accessing/configuring mock

    success, proc_result, error = linux_impl_fixture.perform_device_setup()
    assert success is False
    assert proc_result is None
    assert isinstance(error, TrayAppInitializationError)


def test_linux_impl_perform_device_setup_pkexec_success(linux_impl_fixture: LinuxImpl) -> None:  # mocker removed
    """Tests perform_device_setup() when pkexec helper script execution is successful."""
    linux_impl_fixture._udev_manager.create_rules_interactive.return_value = True  # noqa: SLF001 # Accessing/configuring mock
    # Mock path, not creating actual temp file
    mock_udev_details = {"temp_file_path": "/tmp/temp.rules", "final_file_path": "/etc/final.rules"}  # noqa: S108 # Mock path, not a security risk.
    linux_impl_fixture._udev_manager.get_last_udev_setup_details.return_value = mock_udev_details  # noqa: SLF001 # Accessing/configuring mock

    mock_completed_process = subprocess.CompletedProcess(
        args=["pkexec", "/path/to/script.sh", "/tmp/temp.rules", "/etc/final.rules"],  # noqa: S108
        returncode=PKEXEC_EXIT_SUCCESS,
        stdout="Success",
        stderr="",
    )
    with patch.object(
        linux_impl_fixture,
        "_execute_udev_helper_script",
        return_value=mock_completed_process,
    ) as mock_exec_script:
        success, proc_result, error = linux_impl_fixture.perform_device_setup()

    assert success is True
    assert proc_result == mock_completed_process
    assert error is None
    mock_exec_script.assert_called_once_with(mock_udev_details["temp_file_path"], mock_udev_details["final_file_path"])


@pytest.mark.parametrize(
    ("pkexec_returncode", "expected_success"),  # PT006
    [
        (PKEXEC_EXIT_USER_CANCELLED, False),
        (PKEXEC_EXIT_AUTH_FAILED, False),
        (PKEXEC_EXIT_OTHER_ERROR, False),
    ],
)
def test_linux_impl_perform_device_setup_pkexec_script_failures(
    linux_impl_fixture: LinuxImpl,
    pkexec_returncode: int,
    *, # Ensures expected_success is keyword-only
    expected_success: bool,
) -> None:  # mocker removed
    """Tests perform_device_setup() for various pkexec script failure scenarios."""
    linux_impl_fixture._udev_manager.create_rules_interactive.return_value = True  # noqa: SLF001 # Mock setup
    # Mock path, not creating actual temp file
    mock_udev_details = {"temp_file_path": "/tmp/temp.rules", "final_file_path": "/etc/final.rules"}  # noqa: S108 # Mock path, not a security risk.
    linux_impl_fixture._udev_manager.get_last_udev_setup_details.return_value = mock_udev_details  # noqa: SLF001 # Mock setup

    mock_completed_process = subprocess.CompletedProcess(
        args=[],
        returncode=pkexec_returncode,
        stdout="",
        stderr="Script error",
    )
    with patch.object(
        linux_impl_fixture,
        "_execute_udev_helper_script",
        return_value=mock_completed_process,
    ) as mock_exec_script:
        success, proc_result, error = linux_impl_fixture.perform_device_setup()

    assert success is expected_success
    assert proc_result == mock_completed_process
    assert error is None
    mock_exec_script.assert_called_once()


@pytest.mark.parametrize(
    ("exception_to_raise", "expected_exception_type"),  # PT006
    [
        (TrayAppInitializationError("pkexec not found"), TrayAppInitializationError),
        (Exception("Unexpected general error"), Exception),
    ],
)
def test_linux_impl_perform_device_setup_exceptions(
    linux_impl_fixture: LinuxImpl,
    exception_to_raise: Exception,
    expected_exception_type: type[Exception],
) -> None:  # mocker removed
    """Tests perform_device_setup() when _execute_udev_helper_script raises exceptions."""
    linux_impl_fixture._udev_manager.create_rules_interactive.return_value = True  # noqa: SLF001 # Mock setup
    linux_impl_fixture._udev_manager.create_rules_interactive.return_value = True  # noqa: SLF001 # Mock setup
    # Mock path, not creating actual temp file
    mock_udev_details = {"temp_file_path": "/tmp/temp.rules", "final_file_path": "/etc/final.rules"}  # noqa: S108 # Mock path, not a security risk.
    linux_impl_fixture._udev_manager.get_last_udev_setup_details.return_value = mock_udev_details  # noqa: SLF001 # Mock setup

    with patch.object(
        linux_impl_fixture,
        "_execute_udev_helper_script",
        side_effect=exception_to_raise,
    ) as mock_exec_script:
        success, proc_result, error = linux_impl_fixture.perform_device_setup()

    assert success is False
    assert proc_result is None
    assert isinstance(error, expected_exception_type)
    mock_exec_script.assert_called_once()

    def test_linux_impl_internal_execute_helper_script_calls_subprocess_run(linux_impl_fixture: LinuxImpl) -> None:
        """Tests the internal _execute_udev_helper_script method's call to subprocess.run."""
        temp_path = "/tmp/test.rules"  # noqa: S108 # Mock path, not creating actual temp file.
        final_path = "/etc/test.rules"
        dummy_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        # This is the string we expect helper_script_path to represent
        expected_script_path_str = "/some/path/to/scripts/install-udev-rules.sh"

        with (
            patch("headsetcontrol_tray.os_layer.linux.Path") as mock_path_constructor,
            patch("subprocess.run", return_value=dummy_proc) as mock_run,
        ):
            # Configure the mock Path object that will be returned by Path()
            # when it's used to construct the helper_script_path in LinuxImpl._execute_udev_helper_script
            mock_script_path_obj = MagicMock()  # Removed spec=Path
            mock_script_path_obj.is_file.return_value = True
            # Crucially, mock the __str__ method
            mock_script_path_obj.__str__.return_value = expected_script_path_str  # type: ignore [attr-defined]

            # This mock will represent Path(__file__) inside LinuxImpl._execute_udev_helper_script
            mock_file_dunder_path_obj = MagicMock()  # Removed spec=Path

            # Setup .parent chain and __truediv__ to eventually return mock_script_path_obj
            mock_file_dunder_path_obj.parent = MagicMock()
            mock_file_dunder_path_obj.parent.parent = MagicMock()
            scripts_dir_mock = MagicMock()  # Restored definition
            scripts_dir_mock.resolve = MagicMock() # Ensure resolve is a mock for call
            # This chain simulates (Path(__file__).parent / ".." / ".." / "scripts")
            mock_file_dunder_path_obj.parent.parent.__truediv__.return_value = scripts_dir_mock
            scripts_dir_mock.resolve.return_value = scripts_dir_mock  # .resolve()
            # scripts_dir_mock / "install-udev-rules.sh"
            scripts_dir_mock.__truediv__.return_value = mock_script_path_obj

            # Default side effect for Path() constructor
            def path_side_effect(value: Any) -> MagicMock:
                # If Path() is called with a string that looks like a filename for __file__
                # (this is fragile, assuming linux.py is the context)
                if isinstance(value, str) and "linux.py" in value:  # Heuristic
                    return mock_file_dunder_path_obj
                # For other Path calls, return a generic mock that won't break things
                # This part might not be strictly necessary if all Path usages in the method are covered
                generic_path_mock = MagicMock()
                generic_path_mock.is_file = MagicMock(return_value=True)  # Ensure is_file is a mock
                generic_path_mock.__str__.return_value = str(value) if value else "."  # type: ignore [attr-defined]
                return generic_path_mock

            mock_path_constructor.side_effect = path_side_effect

            # Testing private method directly as it contains complex path logic.
            result = linux_impl_fixture._execute_udev_helper_script(temp_path, final_path)  # noqa: SLF001 # Testing private method

            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0]  # Get the first positional argument (the list)
            assert call_args[0] == "pkexec"
            # call_args[1] should now be the string from mock_script_path_obj.__str__
            assert call_args[1] == expected_script_path_str
            assert call_args[1].endswith("install-udev-rules.sh")  # This should now pass
            assert call_args[2] == temp_path
            assert call_args[3] == final_path
            assert result == dummy_proc
