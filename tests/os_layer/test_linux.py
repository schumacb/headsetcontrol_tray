import os
import platform
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch # Ensure patch is imported

import pytest

# Ensure imports for tested classes are correct
from headsetcontrol_tray.os_layer.linux import LinuxImpl, LinuxHIDManager
from headsetcontrol_tray.os_layer.base import HIDManagerInterface
from headsetcontrol_tray.exceptions import TrayAppInitializationError
from headsetcontrol_tray.app_config import APP_NAME # For path checking

# Mock constants for pkexec exit codes (mirroring app.py or LinuxImpl)
PKEXEC_EXIT_SUCCESS = 0
PKEXEC_EXIT_USER_CANCELLED = 126
PKEXEC_EXIT_AUTH_FAILED = 127
PKEXEC_EXIT_OTHER_ERROR = 1 # Example for other script errors


@pytest.fixture
def linux_impl_fixture(): # mocker removed
    """Fixture to create a LinuxImpl instance with mocked UDEVManager and HIDManager."""
    with patch("headsetcontrol_tray.os_layer.linux.UDEVManager") as mock_udev_manager_class, \
         patch("headsetcontrol_tray.os_layer.linux.LinuxHIDManager") as mock_linux_hid_manager_class:

        mock_udev_manager_instance = MagicMock()
        mock_udev_manager_class.return_value = mock_udev_manager_instance

        mock_linux_hid_manager_instance = MagicMock(spec=LinuxHIDManager)
        mock_linux_hid_manager_class.return_value = mock_linux_hid_manager_instance

        impl = LinuxImpl()
        # Store mocks directly on the instance for tests to access if needed
        impl._udev_manager = mock_udev_manager_instance
        impl._hid_manager = mock_linux_hid_manager_instance
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

def test_linux_impl_internal_execute_helper_script_calls_subprocess_run(linux_impl_fixture): # mocker removed
    temp_path = "/tmp/test.rules"
    final_path = "/etc/test.rules"
    dummy_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")

    # Mocking Path object behavior for script path resolution
    mock_script_file_path = MagicMock(spec=Path)
    mock_script_file_path.is_file.return_value = True

    mock_path_constructor_linux_file = MagicMock(spec=Path)
    mock_path_constructor_linux_file.parent = MagicMock(spec=Path) # for Path(__file__).parent
    # This parent needs to be chainable for ../../..
    parent_of_parent = MagicMock(spec=Path)
    parent_of_parent.parent = MagicMock(spec=Path) # for Path(__file__).parent.parent.parent
    mock_path_constructor_linux_file.parent.parent = parent_of_parent

    # When Path() is called for the script, it should return the mock_script_file_path
    # This is complex because Path() is used for __file__ and then for constructing the script path.
    def complex_path_side_effect(value):
        if str(value).endswith("install-udev-rules.sh"):
            return mock_script_file_path
        # For Path(__file__)
        elif str(value) == __file__ : # This won't work as __file__ is this test file. Need to mock Path for linux.py's __file__
             # This part is tricky as __file__ is dynamic.
             # Let's assume the path construction up to "scripts" dir is what we want to mock.
             # A more robust mock for Path within the tested method context:
            path_mock = MagicMock(spec=Path)
            path_mock.parent.parent.parent.__truediv__.return_value = mock_script_file_path # Mocks scripts_dir / "install-udev-rules.sh"
            path_mock.is_file.return_value = True # For other is_file checks if any
            path_mock.resolve.return_value = path_mock # Resolve returns self
            return path_mock

        # Default Path mock
        default_path_mock = MagicMock(spec=Path)
        default_path_mock.is_file.return_value = True # Default to file existing
        default_path_mock.resolve.return_value = default_path_mock
        return default_path_mock

    # The path to script is (Path(__file__).parent / ".." / ".." / "scripts").resolve() / "install-udev-rules.sh"
    # We need to mock Path() calls within _execute_udev_helper_script
    # Patching 'headsetcontrol_tray.os_layer.linux.Path' is key
    with patch("headsetcontrol_tray.os_layer.linux.Path") as mock_path_in_linux_module, \
         patch("subprocess.run", return_value=dummy_proc) as mock_run:

        # Configure the mock_path_in_linux_module
        # When Path() is called in linux.py, it returns a mock.
        # Path(__file__) in linux.py -> returns a mock representing linux.py's path
        # That mock's .parent.parent... sequence should lead to the script.

        # Simplified: Assume the Path object for the script itself will eventually call is_file()
        # and we make that return True.
        mock_constructed_script_path = MagicMock(spec=Path)
        mock_constructed_script_path.is_file.return_value = True

        # Make Path() constructor return a path that, when / "install-udev-rules.sh" is called,
        # returns our mock_constructed_script_path
        def path_constructor_side_effect(arg):
            # If Path() is called with __file__ (inside linux.py)
            if str(arg).endswith('linux.py'): # A bit fragile, depends on how __file__ is resolved
                # Return a mock that allows parent navigation
                p_mock = MagicMock(spec=Path)
                # p_mock.parent.parent.__truediv__.return_value = mock_constructed_script_path # for scripts_dir / name

                # Let's make it simpler: Path() returns a mock that has a is_file method.
                # The script path is constructed like: (Path(__file__).parent / "../../scripts").resolve() / "install-udev-rules.sh"
                # If Path() itself returns a mock that has is_file=True, it might work.
                # This is hard to get right without seeing the exact Path calls in _execute_udev_helper_script.
                # Let's assume Path(...).is_file() on the script path will be True.
                # The most crucial part is mocking subprocess.run.

                # To make this work, assume the script path exists.
                # The test is primarily about the call to subprocess.run.
                # We can mock the `is_file` check directly on the specific path object if needed,
                # but that's complex. For now, let's assume the script exists.
                # The following mock setup for Path might not be perfect but aims to allow the test to proceed.
                final_path_mock = MagicMock(spec=Path)
                final_path_mock.is_file.return_value = True # This is for the script path check

                # if arg is some path, make it chainable to produce final_path_mock for the script
                # This is still very complex. The easiest is to patch `is_file` on the specific Path instance
                # that is created for the script.

                # Let's try a simpler approach for Path:
                # Any Path instance created will have is_file = True
                instance_mock = MagicMock(spec=Path)
                instance_mock.is_file.return_value = True
                instance_mock.resolve.return_value = instance_mock # Path().resolve()
                # For path segments like .parent or / operator
                instance_mock.parent = instance_mock
                instance_mock.__truediv__ = lambda self, other: instance_mock # path / "segment"
                return instance_mock

            # Default for other Path calls if any
            default_instance_mock = MagicMock(spec=Path)
            default_instance_mock.is_file.return_value = True
            return default_instance_mock

        mock_path_in_linux_module.side_effect = path_constructor_side_effect

        result = linux_impl_fixture._execute_udev_helper_script(temp_path, final_path)

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "pkexec"
        assert isinstance(call_args[1], str) # Script path
        assert call_args[1].endswith("install-udev-rules.sh")
        assert call_args[2] == temp_path
        assert call_args[3] == final_path
        assert result == dummy_proc
