"""Tests for the HIDConnectionManager class."""

# Standard library imports
from pathlib import Path
import sys
from typing import Any
import unittest
from unittest import mock  # Python 3.3+
from unittest.mock import ANY, MagicMock, patch  # Ensure ANY is imported

# Third-party imports
import hid

# Code to modify sys.path must come before application-specific imports
# Ensure src is in path for imports
sys.path.insert(
    0,
    str((Path(__file__).parent / ".." / "src").resolve()),
)

# Application-specific imports
from headsetcontrol_tray import app_config
from headsetcontrol_tray.hid_manager import HIDConnectionManager

# Constants for test assertions
EXPECTED_HID_OPEN_ATTEMPTS_ON_FAILURE = 2


# Default mock device info structure
def create_mock_device_info(
    pid: int,
    interface_number: int = -1,
    usage_page: int = 0,
    usage: int = 0,
    path_suffix: str = "1",
) -> dict[str, Any]:
    """Helper function to create mock HID device info dictionaries for tests."""
    return {
        "vendor_id": app_config.STEELSERIES_VID,
        "product_id": pid,
        "interface_number": interface_number,
        "usage_page": usage_page,
        "usage": usage,
        "path": f"path_vid_{app_config.STEELSERIES_VID:04x}_pid_{pid:04x}_{path_suffix}".encode(),
        "product_string": f"MockDevice PID {pid:04x}",
    }


class TestHIDConnectionManagerDiscovery(unittest.TestCase):
    """Tests HID device discovery functionalities of HIDConnectionManager."""

    def setUp(self) -> None:
        """Set up for HID connection manager discovery tests."""
        self.manager = HIDConnectionManager()

    @patch("headsetcontrol_tray.hid_manager.hid.enumerate")
    @patch("headsetcontrol_tray.hid_manager.logger")  # Restored
    def test_find_potential_hid_devices_success(
        self,
        _mock_logger: MagicMock,  # noqa: PT019
        mock_hid_enumerate: MagicMock,
    ) -> None:  # Restored _mock_logger
        """Test successful discovery of potential HID devices."""
        mock_dev1_pid = app_config.TARGET_PIDS[0]
        mock_dev_other_vid_pid = 0x9999

        mock_hid_enumerate.return_value = [
            create_mock_device_info(mock_dev1_pid),
            create_mock_device_info(
                mock_dev_other_vid_pid,
            ),  # Belongs to SteelSeries VID, but not target PID
            {
                "vendor_id": 0x1234,
                "product_id": 0x5678,
                "path": b"other_path",
            },  # Different VID
        ]

        devices = self.manager.find_potential_hid_devices()
        assert len(devices) == 1
        assert devices[0]["product_id"] == mock_dev1_pid
        mock_hid_enumerate.assert_called_once_with(app_config.STEELSERIES_VID, 0)

    @patch("headsetcontrol_tray.hid_manager.hid.enumerate")
    @patch("headsetcontrol_tray.hid_manager.logger")
    def test_find_potential_hid_devices_enumeration_error(
        self,
        mock_logger: MagicMock,
        mock_hid_enumerate: MagicMock,
    ) -> None:
        """Test find_potential_hid_devices handles hid.enumerate errors."""
        mock_hid_enumerate.side_effect = hid.HIDException("Enumeration failed")
        devices = self.manager.find_potential_hid_devices()
        assert len(devices) == 0
        mock_logger.exception.assert_called_with("Error enumerating HID devices: %s", ANY)

    @patch("headsetcontrol_tray.hid_manager.hid.enumerate")
    @patch("headsetcontrol_tray.hid_manager.logger")  # Restored
    def test_find_potential_hid_devices_no_matches(
        self,
        _mock_logger: MagicMock,  # noqa: PT019 # Restored
        mock_hid_enumerate: MagicMock,
    ) -> None:
        """Test find_potential_hid_devices handles no matching devices found."""
        mock_hid_enumerate.return_value = [
            create_mock_device_info(0x9999),  # Wrong PID
            {
                "vendor_id": 0x1234,
                "product_id": 0x5678,
                "path": b"other_path",
            },  # Different VID
        ]
        devices = self.manager.find_potential_hid_devices()
        assert len(devices) == 0


class TestHIDConnectionManagerSorting(unittest.TestCase):
    """Tests HID device sorting logic within HIDConnectionManager."""

    _original_target_pids = None  # Class attribute for backup

    def setUp(self) -> None:
        """Set up for HID device sorting tests."""
        self.manager = HIDConnectionManager()
        # Backup TARGET_PIDS before each test in this class if necessary, or use setUpClass
        if TestHIDConnectionManagerSorting._original_target_pids is None:
            TestHIDConnectionManagerSorting._original_target_pids = list(
                app_config.TARGET_PIDS,
            )

    def tearDown(self) -> None:
        """Clean up after HID device sorting tests."""
        # Restore TARGET_PIDS after each test if it was backed up and potentially modified
        if TestHIDConnectionManagerSorting._original_target_pids is not None:
            app_config.TARGET_PIDS = list(
                TestHIDConnectionManagerSorting._original_target_pids,
            )
            # Reset for next test, so setUpClass logic isn't strictly needed if we reset here
            # Or, manage this in setUpClass & tearDownClass. For simplicity here, this works per test.

    def test_sort_hid_devices(self) -> None:
        """Test the sorting logic for HID devices based on priority criteria."""
        # Create devices with attributes that will affect sort order
        # Exact match (highest priority: -2)
        dev_a = create_mock_device_info(
            app_config.TARGET_PIDS[0],
            interface_number=app_config.HID_REPORT_INTERFACE,
            usage_page=app_config.HID_REPORT_USAGE_PAGE,
            usage=app_config.HID_REPORT_USAGE_ID,
            path_suffix="dev_a",
        )
        # PID 0x2202 and interface 0 (priority: -1)
        # Ensure 0x2202 is in TARGET_PIDS for it to be found by _find_potential_hid_devices first
        pid_2202 = 0x2202
        if pid_2202 not in app_config.TARGET_PIDS:  # Add it if not present for test setup
            app_config.TARGET_PIDS.append(pid_2202)

        dev_b = create_mock_device_info(
            pid_2202,  # Typically ARCTIS_NOVA_7_USER_PID
            interface_number=0,
            path_suffix="dev_b",
        )
        # Interface 3 (priority: 0)
        dev_c = create_mock_device_info(
            app_config.TARGET_PIDS[0],
            interface_number=3,
            path_suffix="dev_c",
        )
        # Usage page 0xFFC0 (priority: 1)
        dev_d = create_mock_device_info(
            app_config.TARGET_PIDS[0],
            usage_page=0xFFC0,
            path_suffix="dev_d",
        )
        # Default (priority: 2)
        dev_e = create_mock_device_info(
            app_config.TARGET_PIDS[0],
            interface_number=1,
            path_suffix="dev_e",
        )

        devices_unsorted = [dev_e, dev_c, dev_a, dev_d, dev_b]
        expected_order = [dev_a, dev_b, dev_c, dev_d, dev_e]  # Based on sort keys

        sorted_devices = self.manager.sort_hid_devices(devices_unsorted)
        assert [d["path"] for d in sorted_devices] == [e["path"] for e in expected_order]

        # No explicit cleanup here needed due to tearDown,
        # but ensure test logic that modifies app_config.TARGET_PIDS is careful.
        if (
            TestHIDConnectionManagerSorting._original_target_pids is not None
            and pid_2202 not in TestHIDConnectionManagerSorting._original_target_pids
            and pid_2202 in app_config.TARGET_PIDS
        ):
            # This condition means pid_2202 was added for the test, wasn't in original,
            # is not None, and is still in app_config.TARGET_PIDS (tearDown will handle it).
            pass


# Removed class-level patches:
# @patch("headsetcontrol_tray.hid_manager.hid.Device")
# @patch.object(HIDConnectionManager, "_find_potential_hid_devices")


class TestHIDConnectionManagerConnection(unittest.TestCase):
    """Tests HID device connection logic of HIDConnectionManager."""

    def setUp(self) -> None:
        """Set up for HID device connection tests."""
        self.manager = HIDConnectionManager()

    @patch("headsetcontrol_tray.hid_manager.hid.Device")
    @patch.object(HIDConnectionManager, "sort_hid_devices") # Add patch for sort_hid_devices
    @patch.object(HIDConnectionManager, "find_potential_hid_devices") # Corrected patch target
    def test_connect_device_success(
        self,
        mock_find_devices: MagicMock, # Corrected name
        mock_sort_devices: MagicMock, # Add mock for sort_hid_devices
        mock_hid_device_constructor: MagicMock,
    ) -> None:
        """Test successful connection to a HID device."""
        mock_device_info = create_mock_device_info(
            app_config.TARGET_PIDS[0],
            interface_number=app_config.HID_REPORT_INTERFACE,
        )
        mock_find_devices.return_value = [mock_device_info]
        # Make sort_hid_devices return the devices as is for this test
        mock_sort_devices.side_effect = lambda devices: devices

        mock_hid_instance = MagicMock(spec=hid.Device)
        mock_hid_device_constructor.return_value = mock_hid_instance

        hid_device, dev_info = self.manager.connect_device()

        assert hid_device is not None
        assert dev_info is not None
        assert self.manager.hid_device is not None
        assert self.manager.hid_device == mock_hid_instance
        assert self.manager.selected_device_info == mock_device_info
        mock_find_devices.assert_called_once()
        mock_hid_device_constructor.assert_called_once_with(
            path=mock_device_info["path"],
        )

    @patch("headsetcontrol_tray.hid_manager.hid.Device")
    @patch.object(HIDConnectionManager, "find_potential_hid_devices") # Corrected patch target
    def test_connect_device_no_devices_found(
        self,
        mock_find_devices: MagicMock, # Corrected name
        mock_hid_device_constructor: MagicMock,
    ) -> None:
        """Test _connect_device handles no devices found by _find_potential_hid_devices."""
        mock_find_devices.return_value = []
        # sort_hid_devices will not be called if find_potential_hid_devices returns empty

        hid_device, dev_info = self.manager.connect_device()

        assert hid_device is None
        assert dev_info is None
        assert self.manager.hid_device is None
        mock_hid_device_constructor.assert_not_called()

    @patch("headsetcontrol_tray.hid_manager.logger")
    @patch("headsetcontrol_tray.hid_manager.hid.Device")
    @patch.object(HIDConnectionManager, "sort_hid_devices") # Add patch for sort_hid_devices
    @patch.object(HIDConnectionManager, "find_potential_hid_devices") # Corrected patch target
    def test_connect_device_open_fails_for_all(
        self,
        mock_find_devices: MagicMock,  # Innermost corrected name
        mock_sort_devices: MagicMock, # Add mock for sort_hid_devices
        mock_hid_device_constructor: MagicMock,  # Inner
        mock_logger: MagicMock,  # Outermost
    ) -> None:
        """Test _connect_device handles hid.Device.open failures for all candidates."""
        mock_dev_info1 = create_mock_device_info(
            app_config.TARGET_PIDS[0],
            path_suffix="fail1",
        )
        mock_dev_info2 = create_mock_device_info(
            app_config.TARGET_PIDS[0],
            path_suffix="fail2",
        )
        mock_find_devices.return_value = [mock_dev_info1, mock_dev_info2]
        # Make sort_hid_devices return the devices as is for this test
        mock_sort_devices.side_effect = lambda devices: devices

        mock_hid_device_constructor.side_effect = hid.HIDException(
            "Failed to open HID device",
        )

        hid_device, dev_info = self.manager.connect_device()

        assert hid_device is None
        assert dev_info is None
        assert self.manager.hid_device is None
        assert mock_hid_device_constructor.call_count == EXPECTED_HID_OPEN_ATTEMPTS_ON_FAILURE  # Tried both devices
        # Corrected to check for logger.warning and match its arguments
        mock_logger.warning.assert_any_call(
            "    Failed to open HID device path %s: %s", # Log format string
            mock.ANY,  # For path_str
            mock.ANY,   # For the exception instance e
        )

    @patch.object(HIDConnectionManager, "connect_device")  # Patch the public connect_device
    def test_ensure_connection_already_connected(
        self,
        mock_connect_device: MagicMock, # Renamed argument
    ) -> None:
        """Test ensure_connection when a device is already connected."""
        self.manager.hid_device = MagicMock(spec=hid.Device)  # Already connected

        result = self.manager.ensure_connection()

        assert result
        mock_connect_device.assert_not_called() # connect_device should not be called

    @patch.object(HIDConnectionManager, "connect_device")  # Patch the public connect_device
    def test_ensure_connection_needs_connection(
        self,
        mock_connect_device: MagicMock, # Renamed argument
    ) -> None:
        """Test ensure_connection when a new connection attempt is needed."""
        self.manager.hid_device = None  # Not connected
        # Simulate successful connection by connect_device by returning a mock HID device and info
        mock_connect_device.return_value = (MagicMock(spec=hid.Device), {})

        result = self.manager.ensure_connection()

        assert result
        mock_connect_device.assert_called_once()


class TestHIDConnectionManagerClose(unittest.TestCase):
    """Tests HID device closing logic of HIDConnectionManager."""

    def setUp(self) -> None:
        """Set up for HID device close operation tests."""
        self.manager = HIDConnectionManager()

    def test_close_device(self) -> None:
        """Test closing an active HID device connection."""
        mock_hid_dev = MagicMock(spec=hid.Device)
        # Simulate selected_device_info having a path for logging purposes
        self.manager.selected_device_info = {"path": b"/dev/mock_hid"}
        self.manager.hid_device = mock_hid_dev

        self.manager.close()

        mock_hid_dev.close.assert_called_once()
        assert self.manager.hid_device is None
        assert self.manager.selected_device_info is None

    def test_close_no_device(self) -> None:
        """Test close operation when no HID device is connected."""
        self.manager.hid_device = None
        self.manager.selected_device_info = None

        # Should not raise any error
        self.manager.close()
        assert self.manager.hid_device is None


if __name__ == "__main__":
    # No longer need to set _original_target_pids here as it's handled in setUp/tearDown
    unittest.main()
