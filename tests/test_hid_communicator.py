"""Tests for the HIDCommunicator class."""

import sys # Removed import os
import unittest
from pathlib import Path # Added Path
from unittest.mock import MagicMock, patch

import hid
import pytest  # Added import

# Ensure src is in path for imports
sys.path.insert(
    0,
    str((Path(__file__).parent / ".." / "src").resolve()), # Replaced with pathlib
)

from headsetcontrol_tray.exceptions import HIDCommunicationError
from headsetcontrol_tray.hid_communicator import HIDCommunicator


# Removed class decorator
class TestHIDCommunicator(unittest.TestCase):
    """Tests HID communication functionalities."""

    def setUp(self) -> None:  # Signature changed
        """Set up test environment for HIDCommunicator tests."""
        self.logger_patcher = patch(
            f"{HIDCommunicator.__module__}.logger",
            new_callable=MagicMock,
        )
        self.mock_logger = self.logger_patcher.start()
        self.addCleanup(self.logger_patcher.stop)

        self.mock_hid_device = MagicMock(spec=hid.Device)
        # Simulate a path attribute that can be decoded or is already a string
        self.mock_hid_device.path = b"/dev/mock_hid_path"
        # Note: HIDCommunicator now requires device_info. For tests, provide a minimal mock.
        self.mock_device_info = {
            "path": b"/dev/mock_hid_path",
            "product_string": "Mock HID Device Test",
        }
        self.communicator = HIDCommunicator(self.mock_hid_device, self.mock_device_info)

        self.mock_hid_device.write.reset_mock()
        self.mock_hid_device.read.reset_mock()

        # self.mock_logger is now available

    def test_init_with_none_device_raises_value_error(self) -> None:  # Removed mock_logger arg
        """Test __init__ raises HIDCommunicationError if hid_device is None."""
        with pytest.raises(HIDCommunicationError):
            # Provide a dummy device_info for this specific error test
            HIDCommunicator(None, device_info={"path": b"", "product_string": ""})
        self.mock_logger.error.assert_called_with(
            "HIDCommunicator initialized with a None hid_device. This is unexpected.",
        )

    def test_write_report_success_with_report_id(self) -> None:  # Removed mock_logger arg
        """Test successful HID write operation with a report ID."""
        self.mock_hid_device.write.return_value = 3  # Expected length of b'\x01\x02\x03'

        result = self.communicator.write_report(report_id=0x01, data=[0x02, 0x03])

        assert result
        self.mock_hid_device.write.assert_called_once_with(b"\x01\x02\x03")
        self.mock_logger.debug.assert_any_call("Bytes written: %s", 3)

    def test_write_report_success_no_report_id(self) -> None:  # Removed mock_logger arg
        """Test successful HID write operation without a report ID."""
        self.mock_hid_device.write.return_value = 2  # Expected length of b'\x01\x02'

        result = self.communicator.write_report(report_id=0, data=[0x01, 0x02])

        assert result
        self.mock_hid_device.write.assert_called_once_with(b"\x01\x02")

    def test_write_report_hid_write_returns_zero_bytes(self) -> None:  # Removed mock_logger arg
        """Test write_report handles zero bytes written by hid.Device.write."""
        self.mock_hid_device.write.return_value = 0  # Simulate write returning 0 bytes

        result = self.communicator.write_report(report_id=0x01, data=[0x02, 0x03])

        assert not result
        self.mock_logger.warning.assert_called_with(
            "HID write returned %s. This might indicate an issue with the device %s (%s).",
            0,
            self.communicator.device_product_str,
            self.communicator.device_path_str,
        )

    def test_write_report_hid_write_raises_exception(self) -> None:  # Removed mock_logger arg
        """Test write_report handles HIDException from hid.Device.write."""
        self.mock_hid_device.write.side_effect = hid.HIDException("HID Write Error")

        result = self.communicator.write_report(report_id=0x01, data=[0x02, 0x03])

        assert not result
        # The logger call in the application code is now logger.exception
        self.mock_logger.exception.assert_called_with(
            "HID write error on device %s (%s)",
            self.communicator.device_product_str,
            self.communicator.device_path_str,
        )

    def test_read_report_success(self) -> None:  # Removed mock_logger arg
        """Test successful HID read operation."""
        expected_bytes = b"\x01\x02\x03"
        self.mock_hid_device.read.return_value = bytearray(
            expected_bytes,
        )  # hid.Device.read often returns bytearray

        result = self.communicator.read_report(report_length=3)  # Removed timeout_ms

        assert result == expected_bytes
        self.mock_hid_device.read.assert_called_once_with(
            3,
        )  # Removed timeout_ms from assertion
        self.mock_logger.debug.assert_any_call(
            "HID read successful from %s (%s): %s",
            self.communicator.device_product_str,
            self.communicator.device_path_str,
            expected_bytes.hex(),
        )

    def test_read_report_no_data_returns_none(self) -> None:  # Removed mock_logger arg
        """Test read_report returns None when hid.Device.read returns no data."""
        self.mock_hid_device.read.return_value = bytearray(b"")  # Empty bytearray

        result = self.communicator.read_report(report_length=3)  # timeout_ms removed

        assert result is None
        self.mock_logger.warning.assert_called_with(
            "No data received from HID read on %s (%s) (length %s).",
            self.communicator.device_product_str,
            self.communicator.device_path_str,
            3,
        )  # timeout part removed from log

    def test_read_report_incomplete_data_returns_none(self) -> None:  # Removed mock_logger arg
        """Test read_report returns None when hid.Device.read returns incomplete data."""
        incomplete_bytes = b"\x01\x02"
        self.mock_hid_device.read.return_value = bytearray(incomplete_bytes)

        result = self.communicator.read_report(report_length=3)  # timeout_ms removed

        assert result is None
        self.mock_logger.warning.assert_called_with(
            "Incomplete HID read on %s (%s). Expected %s bytes, got %s: %s",
            self.communicator.device_product_str,
            self.communicator.device_path_str,
            3,
            len(incomplete_bytes),
            incomplete_bytes.hex(),
        )

    def test_read_report_hid_read_raises_exception(self) -> None:  # Removed mock_logger arg
        """Test read_report handles HIDException from hid.Device.read."""
        self.mock_hid_device.read.side_effect = hid.HIDException("HID Read Error")

        result = self.communicator.read_report(report_length=3)  # timeout_ms removed

        assert result is None
        # The logger call in the application code is now logger.exception
        self.mock_logger.exception.assert_called_with(
            "HID read error on device %s (%s)",
            self.communicator.device_product_str,
            self.communicator.device_path_str,
        )


# Removed test_read_report_default_timeout and test_read_report_none_timeout_uses_default
# as timeout_ms parameter is no longer part of read_report method.

if __name__ == "__main__":
    unittest.main()
