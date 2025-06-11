"""Tests for the HIDConnectionManager class."""
import os
import sys
import unittest
from typing import Any # Added
import pytest # Added
from unittest import mock  # Added
from unittest.mock import MagicMock, patch

import hid

# Ensure src is in path for imports
sys.path.insert(
    0,
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")),
)

from headsetcontrol_tray import app_config
from headsetcontrol_tray.hid_manager import HIDConnectionManager


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
    @patch("headsetcontrol_tray.hid_manager.logger") # Restored
    def test_find_potential_hid_devices_success(self, _mock_logger: MagicMock,  # noqa: PT019
                                               mock_hid_enumerate: MagicMock) -> None: # Restored _mock_logger
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

        devices = self.manager._find_potential_hid_devices()
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
        devices = self.manager._find_potential_hid_devices()
        assert len(devices) == 0
        mock_logger.exception.assert_called_with("Error enumerating HID devices")

    @patch("headsetcontrol_tray.hid_manager.hid.enumerate")
    @patch("headsetcontrol_tray.hid_manager.logger") # Restored
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
        devices = self.manager._find_potential_hid_devices()
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
            # TestHIDConnectionManagerSorting._original_target_pids = None

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
        if (
            pid_2202 not in app_config.TARGET_PIDS
        ):  # Add it if not present for test setup
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

        sorted_devices = self.manager._sort_hid_devices(devices_unsorted)
        assert [d["path"] for d in sorted_devices] == [e["path"] for e in expected_order]

        # No explicit cleanup here needed due to tearDown,
        # but ensure test logic that modifies app_config.TARGET_PIDS is careful.
        # The original test had a cleanup:
        # if pid_2202 not in getattr(self, '_original_target_pids', app_config.TARGET_PIDS):
        #    app_config.TARGET_PIDS.remove(pid_2202)
        # This suggests that the original TARGET_PIDS for comparison in getattr should be the class one.
        if pid_2202 not in TestHIDConnectionManagerSorting._original_target_pids:  # type: ignore
            # This condition means pid_2202 was added for the test and wasn't in original
            if (
                pid_2202 in app_config.TARGET_PIDS
            ):  # if it's still there (it should be if tearDown hasn't run)
                pass  # tearDown will handle it. Or remove here if tearDown is not used.
                # app_config.TARGET_PIDS.remove(pid_2202) # If not using tearDown for this.


# Removed class-level patches:
# @patch("headsetcontrol_tray.hid_manager.hid.Device")
# @patch.object(HIDConnectionManager, "_find_potential_hid_devices")

# Removed fixtures:
# @pytest.fixture
# def mock_logger_fixture():
#     with patch("headsetcontrol_tray.hid_manager.logger") as mock_fixture:
#         yield mock_fixture
#
# @pytest.fixture
# def mock_find_devices_unused_fixture():
#     with patch.object(HIDConnectionManager, "_find_potential_hid_devices") as mock_fixture:
#         yield mock_fixture
#
# @pytest.fixture
# def mock_hid_device_constructor_unused_fixture():
#     with patch("headsetcontrol_tray.hid_manager.hid.Device") as mock_fixture:
#         yield mock_fixture


class TestHIDConnectionManagerConnection(unittest.TestCase):
    """Tests HID device connection logic of HIDConnectionManager."""
    def setUp(self) -> None:
        """Set up for HID device connection tests."""
        self.manager = HIDConnectionManager()

    @patch("headsetcontrol_tray.hid_manager.hid.Device")
    @patch.object(HIDConnectionManager, "_find_potential_hid_devices")
    def test_connect_device_success(
        self,
        mock_find_devices: MagicMock,
        mock_hid_device_constructor: MagicMock,
    ) -> None:
        """Test successful connection to a HID device."""
        mock_device_info = create_mock_device_info(
            app_config.TARGET_PIDS[0],
            interface_number=app_config.HID_REPORT_INTERFACE,
        )
        mock_find_devices.return_value = [
            mock_device_info,
        ]  # Already sorted by virtue of being only one

        mock_hid_instance = MagicMock(spec=hid.Device)
        mock_hid_device_constructor.return_value = mock_hid_instance

        result = self.manager._connect_device()

        assert result
        assert self.manager.hid_device is not None
        assert self.manager.hid_device == mock_hid_instance
        assert self.manager.selected_device_info == mock_device_info
        mock_find_devices.assert_called_once()
        mock_hid_device_constructor.assert_called_once_with(
            path=mock_device_info["path"],
        )

    @patch("headsetcontrol_tray.hid_manager.hid.Device")
    @patch.object(HIDConnectionManager, "_find_potential_hid_devices")
    def test_connect_device_no_devices_found(
        self,
        mock_find_devices: MagicMock,
        mock_hid_device_constructor: MagicMock,
    ) -> None:
        """Test _connect_device handles no devices found by _find_potential_hid_devices."""
        mock_find_devices.return_value = []

        result = self.manager._connect_device()

        assert not result
        assert self.manager.hid_device is None
        mock_hid_device_constructor.assert_not_called()

    @patch("headsetcontrol_tray.hid_manager.logger")
    @patch("headsetcontrol_tray.hid_manager.hid.Device")
    @patch.object(HIDConnectionManager, "_find_potential_hid_devices")
    def test_connect_device_open_fails_for_all(
        self,
        mock_find_devices: MagicMock, # Innermost
        mock_hid_device_constructor: MagicMock, # Inner
        mock_logger: MagicMock, # Outermost
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
        mock_find_devices.return_value = [
            mock_dev_info1,
            mock_dev_info2,
        ]  # Assume already sorted

        mock_hid_device_constructor.side_effect = hid.HIDException(
            "Failed to open HID device",
        )

        result = self.manager._connect_device()

        assert not result
        assert self.manager.hid_device is None
        assert mock_hid_device_constructor.call_count == 2  # Tried both devices
        mock_logger.exception.assert_any_call(
            "    Failed to open HID device path %s",
            mock.ANY,
        )

    @patch.object(HIDConnectionManager, "_connect_device") # provides mock_internal_connect_device
    @patch("headsetcontrol_tray.hid_manager.hid.Device") # provides _mock_hid_device_constructor_unused
    @patch.object(HIDConnectionManager, "_find_potential_hid_devices") # provides _mock_find_devices_unused
    def test_ensure_connection_already_connected(
        self,
        _mock_find_devices_unused: MagicMock,  # noqa: PT019
        _mock_hid_device_constructor_unused: MagicMock,  # noqa: PT019
        mock_internal_connect_device: MagicMock,
    ) -> None:
        """Test ensure_connection when a device is already connected."""
        self.manager.hid_device = MagicMock(spec=hid.Device)  # Already connected

        result = self.manager.ensure_connection()

        assert result
        mock_internal_connect_device.assert_not_called()

    @patch.object(HIDConnectionManager, "_connect_device") # provides mock_internal_connect_device
    @patch("headsetcontrol_tray.hid_manager.hid.Device") # provides _mock_hid_device_constructor_unused
    @patch.object(HIDConnectionManager, "_find_potential_hid_devices") # provides _mock_find_devices_unused
    def test_ensure_connection_needs_connection(
        self,
        _mock_find_devices_unused: MagicMock,  # noqa: PT019
        _mock_hid_device_constructor_unused: MagicMock,  # noqa: PT019
        mock_internal_connect_device: MagicMock,
    ) -> None:
        """Test ensure_connection when a new connection attempt is needed."""
        self.manager.hid_device = None  # Not connected
        mock_internal_connect_device.return_value = (
            True  # Simulate successful connection by _connect_device
        )

        result = self.manager.ensure_connection()

        assert result
        mock_internal_connect_device.assert_called_once()


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
