import os
import platform
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

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
def linux_impl_fixture(mocker): # Renamed fixture to avoid conflict
    """Fixture to create a LinuxImpl instance with mocked UDEVManager and HIDManager."""
    # Mock UDEVManager class itself before LinuxImpl instantiates it
    mock_udev_manager_instance = MagicMock()
    mocker.patch("headsetcontrol_tray.os_layer.linux.UDEVManager", return_value=mock_udev_manager_instance)

    # Mock LinuxHIDManager class itself
    mock_linux_hid_manager_instance = MagicMock(spec=LinuxHIDManager)
    mocker.patch("headsetcontrol_tray.os_layer.linux.LinuxHIDManager", return_value=mock_linux_hid_manager_instance)

    impl = LinuxImpl()
    # Store mocks directly on the instance for tests to access if needed,
    # though patching methods on the mocked classes is often cleaner.
    impl._udev_manager = mock_udev_manager_instance
    impl._hid_manager = mock_linux_hid_manager_instance
    return impl

def test_linux_impl_get_os_name(linux_impl_fixture):
    assert linux_impl_fixture.get_os_name() == "linux"

def test_linux_impl_get_hid_manager(linux_impl_fixture, mocker):
    # The fixture already patches LinuxHIDManager, so get_hid_manager() returns the mock
    hid_manager = linux_impl_fixture.get_hid_manager()
    assert isinstance(hid_manager, MagicMock)
    # Check if the mock object (though it's a generic MagicMock here because of the patch)
    # was created based on a class that implements HIDManagerInterface.
    # This is implicitly tested by the spec in the fixture.
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
    assert linux_impl_fixture.needs_device_setup() is False # Corrected based on recent change

# --- Tests for perform_device_setup ---

def test_linux_impl_perform_device_setup_prepare_fails(linux_impl_fixture):
    # Simulate UDEVManager's prepare_udev_rule_details failing
    linux_impl_fixture._udev_manager.prepare_udev_rule_details.return_value = False

    success, proc_result, error = linux_impl_fixture.perform_device_setup()
    assert success is False
    assert proc_result is None
    # Depending on LinuxImpl's perform_device_setup, an error might be returned here
    assert isinstance(error, TrayAppInitializationError)


def test_linux_impl_perform_device_setup_pkexec_success(linux_impl_fixture, mocker):
    linux_impl_fixture._udev_manager.prepare_udev_rule_details.return_value = True
    mock_udev_details = {"temp_file_path": "/tmp/temp.rules", "final_file_path": "/etc/final.rules"}
    linux_impl_fixture._udev_manager.get_last_udev_setup_details.return_value = mock_udev_details

    mock_completed_process = subprocess.CompletedProcess(
        args=["pkexec", "/path/to/script.sh", "/tmp/temp.rules", "/etc/final.rules"],
        returncode=PKEXEC_EXIT_SUCCESS, stdout="Success", stderr=""
    )
    mocker.patch.object(linux_impl_fixture, "_execute_udev_helper_script", return_value=mock_completed_process)

    success, proc_result, error = linux_impl_fixture.perform_device_setup()

    assert success is True
    assert proc_result == mock_completed_process
    assert error is None
    linux_impl_fixture._execute_udev_helper_script.assert_called_once_with(
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
def test_linux_impl_perform_device_setup_pkexec_script_failures(linux_impl_fixture, mocker, pkexec_returncode, expected_success):
    linux_impl_fixture._udev_manager.prepare_udev_rule_details.return_value = True
    mock_udev_details = {"temp_file_path": "/tmp/temp.rules", "final_file_path": "/etc/final.rules"}
    linux_impl_fixture._udev_manager.get_last_udev_setup_details.return_value = mock_udev_details

    mock_completed_process = subprocess.CompletedProcess(
        args=[], returncode=pkexec_returncode, stdout="", stderr="Script error"
    )
    mocker.patch.object(linux_impl_fixture, "_execute_udev_helper_script", return_value=mock_completed_process)

    success, proc_result, error = linux_impl_fixture.perform_device_setup()

    assert success is expected_success
    assert proc_result == mock_completed_process
    assert error is None
    linux_impl_fixture._execute_udev_helper_script.assert_called_once()

@pytest.mark.parametrize(
    "exception_to_raise, expected_exception_type",
    [
        (TrayAppInitializationError("pkexec not found"), TrayAppInitializationError),
        (Exception("Unexpected general error"), Exception),
    ],
)
def test_linux_impl_perform_device_setup_exceptions(linux_impl_fixture, mocker, exception_to_raise, expected_exception_type):
    linux_impl_fixture._udev_manager.prepare_udev_rule_details.return_value = True
    mock_udev_details = {"temp_file_path": "/tmp/temp.rules", "final_file_path": "/etc/final.rules"}
    linux_impl_fixture._udev_manager.get_last_udev_setup_details.return_value = mock_udev_details

    mocker.patch.object(linux_impl_fixture, "_execute_udev_helper_script", side_effect=exception_to_raise)

    success, proc_result, error = linux_impl_fixture.perform_device_setup()

    assert success is False
    assert proc_result is None
    assert isinstance(error, expected_exception_type)
    linux_impl_fixture._execute_udev_helper_script.assert_called_once()

# Test for _execute_udev_helper_script (internal method, but important for coverage)
def test_linux_impl_internal_execute_helper_script_calls_subprocess_run(linux_impl_fixture, mocker):
    mock_run = mocker.patch("subprocess.run")
    dummy_proc = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
    mock_run.return_value = dummy_proc

    temp_path = "/tmp/test.rules"
    final_path = "/etc/test.rules"

    # This complex path mocking is tricky. For robust testing of _execute_udev_helper_script,
    # consider refactoring it to make the script path more easily mockable or injectable.
    # For now, we assume the path logic inside is correct if the subprocess.run is called.
    # A simpler approach if direct path mocking is too complex:
    # Patch Path(...).is_file() globally for the duration of this test for any path.

    # Simplified mocking for Path().is_file() for this specific test
    mock_path_instance = MagicMock(spec=Path)
    mock_path_instance.is_file.return_value = True
    mock_path_instance.resolve.return_value = mock_path_instance # resolve() returns self

    with patch("headsetcontrol_tray.os_layer.linux.Path", return_value=mock_path_instance) as mock_path_constructor:
        # Ensure that Path(__file__) still works somewhat as expected by returning a mock that can be manipulated
        # Path(__file__).parent needs to return a mock Path that can then be used for further path ops
        mock_file_path_obj = MagicMock(spec=Path)
        mock_file_path_obj.parent = mock_path_instance # Path(__file__).parent
        mock_path_constructor.return_value = mock_file_path_obj # Path(__file__) returns this

        # More specific: if Path is constructed with __file__, return the specific mock
        def path_side_effect(arg):
            if arg == __file__:
                return mock_file_path_obj
            # For other Path constructions (like the script path itself)
            new_mock_path = MagicMock(spec=Path)
            new_mock_path.is_file.return_value = True
            new_mock_path.resolve.return_value = new_mock_path
            return new_mock_path

        mock_path_constructor.side_effect = path_side_effect


        result = linux_impl_fixture._execute_udev_helper_script(temp_path, final_path)

        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "pkexec"
        # The actual script path depends on the mocked Path object's behavior.
        # We can assert it's a string and ends with the script name.
        assert isinstance(call_args[1], str)
        assert call_args[1].endswith("install-udev-rules.sh")
        assert call_args[2] == temp_path
        assert call_args[3] == final_path
        assert result == dummy_proc
