import os
import platform
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch # Ensure patch is imported

import pytest

# Ensure imports for tested classes are correct
from headsetcontrol_tray.os_layer.linux import LinuxImpl # Removed LinuxHIDManager
from headsetcontrol_tray.os_layer.base import HIDManagerInterface
from headsetcontrol_tray.exceptions import TrayAppInitializationError
from headsetcontrol_tray.app_config import APP_NAME # For path checking
# Import HIDConnectionManager for mocking
from headsetcontrol_tray.hid_manager import HIDConnectionManager

# Mock constants for pkexec exit codes (mirroring app.py or LinuxImpl)
PKEXEC_EXIT_SUCCESS = 0
PKEXEC_EXIT_USER_CANCELLED = 126
PKEXEC_EXIT_AUTH_FAILED = 127
PKEXEC_EXIT_OTHER_ERROR = 1 # Example for other script errors


@pytest.fixture
def linux_impl_fixture(): # mocker removed
    """Fixture to create a LinuxImpl instance with mocked UDEVManager and HIDManager."""
    with patch("headsetcontrol_tray.os_layer.linux.UDEVManager") as mock_udev_manager_class, \
         patch("headsetcontrol_tray.os_layer.linux.HIDConnectionManager") as mock_hid_manager_class: # Patched HIDConnectionManager

        mock_udev_manager_instance = MagicMock()
        mock_udev_manager_class.return_value = mock_udev_manager_instance

        mock_hid_manager_instance = MagicMock(spec=HIDConnectionManager) # Mock HIDConnectionManager
        mock_hid_manager_class.return_value = mock_hid_manager_instance

        impl = LinuxImpl()
        # Store mocks directly on the instance for tests to access if needed
        impl._udev_manager = mock_udev_manager_instance
        impl._hid_manager = mock_hid_manager_instance # Assign the correct mock
        yield impl # Use yield for pytest fixtures

def test_linux_impl_get_os_name(linux_impl_fixture):
    assert linux_impl_fixture.get_os_name() == "linux"

def test_linux_impl_get_hid_manager(linux_impl_fixture): # mocker removed
    hid_manager = linux_impl_fixture.get_hid_manager()
    assert isinstance(hid_manager, MagicMock)
    assert isinstance(linux_impl_fixture._hid_manager, HIDManagerInterface)


@pytest.mark.parametrize(
    "xdg_home, expected_parent, expected_name_part",
    [
        ("/custom/config", Path("/custom/config"), APP_NAME.lower().replace(" ", "_")),
        (None, Path.home() / ".config", APP_NAME.lower().replace(" ", "_")),
    ],
)
def test_linux_impl_get_config_dir(linux_impl_fixture, xdg_home, expected_parent, expected_name_part):
    env_vars = {}
    if xdg_home:
        env_vars["XDG_CONFIG_HOME"] = xdg_home

    with patch.dict(os.environ, env_vars, clear=True):
        config_dir = linux_impl_fixture.get_config_dir()
        assert config_dir.name == expected_name_part
        assert config_dir.parent == expected_parent

@pytest.mark.parametrize(
    "xdg_home, expected_parent, expected_name_part",
    [
        ("/custom/data", Path("/custom/data"), APP_NAME.lower().replace(" ", "_")),
        (None, Path.home() / ".local" / "share", APP_NAME.lower().replace(" ", "_")),
    ],
)
def test_linux_impl_get_data_dir(linux_impl_fixture, xdg_home, expected_parent, expected_name_part):
    env_vars = {}
    if xdg_home:
        env_vars["XDG_DATA_HOME"] = xdg_home

    with patch.dict(os.environ, env_vars, clear=True):
        data_dir = linux_impl_fixture.get_data_dir()
        assert data_dir.name == expected_name_part
        assert data_dir.parent == expected_parent


def test_linux_impl_needs_device_setup_rules_not_installed(linux_impl_fixture):
    linux_impl_fixture._udev_manager.are_rules_installed.return_value = False
    assert linux_impl_fixture.needs_device_setup() is True

def test_linux_impl_needs_device_setup_rules_installed(linux_impl_fixture):
    linux_impl_fixture._udev_manager.are_rules_installed.return_value = True
    assert linux_impl_fixture.needs_device_setup() is False

# --- Tests for perform_device_setup ---

def test_linux_impl_perform_device_setup_prepare_fails(linux_impl_fixture):
    linux_impl_fixture._udev_manager.prepare_udev_rule_details.return_value = False

    success, proc_result, error = linux_impl_fixture.perform_device_setup()
    assert success is False
    assert proc_result is None
    assert isinstance(error, TrayAppInitializationError)


def test_linux_impl_perform_device_setup_pkexec_success(linux_impl_fixture): # mocker removed
    linux_impl_fixture._udev_manager.prepare_udev_rule_details.return_value = True
    mock_udev_details = {"temp_file_path": "/tmp/temp.rules", "final_file_path": "/etc/final.rules"}
    linux_impl_fixture._udev_manager.get_last_udev_setup_details.return_value = mock_udev_details

    mock_completed_process = subprocess.CompletedProcess(
        args=["pkexec", "/path/to/script.sh", "/tmp/temp.rules", "/etc/final.rules"],
        returncode=PKEXEC_EXIT_SUCCESS, stdout="Success", stderr=""
    )
    with patch.object(linux_impl_fixture, "_execute_udev_helper_script", return_value=mock_completed_process) as mock_exec_script:
        success, proc_result, error = linux_impl_fixture.perform_device_setup()

    assert success is True
    assert proc_result == mock_completed_process
    assert error is None
    mock_exec_script.assert_called_once_with(
        mock_udev_details["temp_file_path"], mock_udev_details["final_file_path"]
    )

@pytest.mark.parametrize(
    "pkexec_returncode, expected_success",
    [
        (PKEXEC_EXIT_USER_CANCELLED, False),
        (PKEXEC_EXIT_AUTH_FAILED, False),
        (PKEXEC_EXIT_OTHER_ERROR, False),
    ],
)
def test_linux_impl_perform_device_setup_pkexec_script_failures(linux_impl_fixture, pkexec_returncode, expected_success): # mocker removed
    linux_impl_fixture._udev_manager.prepare_udev_rule_details.return_value = True
    mock_udev_details = {"temp_file_path": "/tmp/temp.rules", "final_file_path": "/etc/final.rules"}
    linux_impl_fixture._udev_manager.get_last_udev_setup_details.return_value = mock_udev_details

    mock_completed_process = subprocess.CompletedProcess(
        args=[], returncode=pkexec_returncode, stdout="", stderr="Script error"
    )
    with patch.object(linux_impl_fixture, "_execute_udev_helper_script", return_value=mock_completed_process) as mock_exec_script:
        success, proc_result, error = linux_impl_fixture.perform_device_setup()

    assert success is expected_success
    assert proc_result == mock_completed_process
    assert error is None
    mock_exec_script.assert_called_once()

@pytest.mark.parametrize(
    "exception_to_raise, expected_exception_type",
    [
        (TrayAppInitializationError("pkexec not found"), TrayAppInitializationError),
        (Exception("Unexpected general error"), Exception),
    ],
)
def test_linux_impl_perform_device_setup_exceptions(linux_impl_fixture, exception_to_raise, expected_exception_type): # mocker removed
    linux_impl_fixture._udev_manager.prepare_udev_rule_details.return_value = True
    mock_udev_details = {"temp_file_path": "/tmp/temp.rules", "final_file_path": "/etc/final.rules"}
    linux_impl_fixture._udev_manager.get_last_udev_setup_details.return_value = mock_udev_details

    with patch.object(linux_impl_fixture, "_execute_udev_helper_script", side_effect=exception_to_raise) as mock_exec_script:
        success, proc_result, error = linux_impl_fixture.perform_device_setup()

    assert success is False
    assert proc_result is None
    assert isinstance(error, expected_exception_type)
    mock_exec_script.assert_called_once()

    def test_linux_impl_internal_execute_helper_script_calls_subprocess_run(linux_impl_fixture):
        temp_path = "/tmp/test.rules"
        final_path = "/etc/test.rules"
        dummy_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

        # This is the string we expect helper_script_path to represent
        expected_script_path_str = "/some/path/to/scripts/install-udev-rules.sh"

        with patch("headsetcontrol_tray.os_layer.linux.Path") as mock_path_constructor, \
             patch("subprocess.run", return_value=dummy_proc) as mock_run:

            # Configure the mock Path object that will be returned by Path()
            # when it's used to construct the helper_script_path in LinuxImpl._execute_udev_helper_script
            mock_script_path_obj = MagicMock(spec=Path)
            mock_script_path_obj.is_file.return_value = True
            # Crucially, mock the __str__ method
            mock_script_path_obj.__str__.return_value = expected_script_path_str

            # This mock will represent Path(__file__) inside LinuxImpl._execute_udev_helper_script
            mock_file_dunder_path_obj = MagicMock(spec=Path)

            # Setup .parent chain and __truediv__ to eventually return mock_script_path_obj
            # Path(__file__).parent
            mock_file_dunder_path_obj.parent = MagicMock(spec=Path)
            # Path(__file__).parent.parent
            mock_file_dunder_path_obj.parent.parent = MagicMock(spec=Path)
            # Path(__file__).parent.parent / ".." -> should still be a Path-like mock
            # (Path(__file__).parent / ".." / ".." / "scripts").resolve()
            scripts_dir_mock = MagicMock(spec=Path)
            # This chain simulates (Path(__file__).parent / ".." / ".." / "scripts")
            mock_file_dunder_path_obj.parent.parent.__truediv__.return_value = scripts_dir_mock
            scripts_dir_mock.resolve.return_value = scripts_dir_mock # .resolve()
            # scripts_dir_mock / "install-udev-rules.sh"
            scripts_dir_mock.__truediv__.return_value = mock_script_path_obj

            # Default side effect for Path() constructor
            def path_side_effect(value):
                # If Path() is called with a string that looks like a filename for __file__
                # (this is fragile, assuming linux.py is the context)
                if isinstance(value, str) and 'linux.py' in value: # Heuristic
                    return mock_file_dunder_path_obj
                # For other Path calls, return a generic mock that won't break things
                # This part might not be strictly necessary if all Path usages in the method are covered
                generic_path_mock = MagicMock(spec=Path)
                generic_path_mock.is_file.return_value = True # Default to file existing
                generic_path_mock.__str__.return_value = str(value) if value else "." # So str(Path(x)) == x
                return generic_path_mock

            mock_path_constructor.side_effect = path_side_effect

            result = linux_impl_fixture._execute_udev_helper_script(temp_path, final_path)

            mock_run.assert_called_once()
            call_args = mock_run.call_args[0][0] # Get the first positional argument (the list)
            assert call_args[0] == "pkexec"
            # call_args[1] should now be the string from mock_script_path_obj.__str__
            assert call_args[1] == expected_script_path_str
            assert call_args[1].endswith("install-udev-rules.sh") # This should now pass
            assert call_args[2] == temp_path
            assert call_args[3] == final_path
            assert result == dummy_proc
