import unittest
from unittest.mock import MagicMock, patch, call
import hid # type: ignore[import-not-found]
import sys
import os

# Ensure src is in path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from headsetcontrol_tray.hid_communicator import HIDCommunicator
from headsetcontrol_tray import app_config # For logger name

# Patch the logger at the module level where HIDCommunicator uses it
@patch(f"{HIDCommunicator.__module__}.logger", new_callable=MagicMock)
class TestHIDCommunicator(unittest.TestCase):

    def setUp(self, mock_logger_unused): # mock_logger_unused because it's patched at class level
        self.mock_hid_device = MagicMock(spec=hid.Device)
        # Simulate a path attribute that can be decoded or is already a string
        self.mock_hid_device.path = b'/dev/mock_hid_path'
        self.communicator = HIDCommunicator(self.mock_hid_device)
        # Reset mocks that might be part of the HIDDevice mock spec if needed, e.g. write, read
        self.mock_hid_device.write.reset_mock()
        self.mock_hid_device.read.reset_mock()

        # Access the class-level logger mock if needed for assertions on logger calls specifically within HIDCommunicator
        self.mock_logger = mock_logger_unused


    def test_init_with_none_device_raises_value_error(self, mock_logger):
        with self.assertRaises(ValueError):
            HIDCommunicator(None) # type: ignore
        mock_logger.error.assert_called_with("HIDCommunicator initialized with a None hid_device. This is unexpected.")

    def test_write_report_success_with_report_id(self, mock_logger):
        self.mock_hid_device.write.return_value = 3 # Expected length of b'\x01\x02\x03'

        result = self.communicator.write_report(report_id=0x01, data=[0x02, 0x03])

        self.assertTrue(result)
        self.mock_hid_device.write.assert_called_once_with(b'\x01\x02\x03')
        mock_logger.debug.assert_any_call("Bytes written: 3")


    def test_write_report_success_no_report_id(self, mock_logger):
        self.mock_hid_device.write.return_value = 2 # Expected length of b'\x01\x02'

        result = self.communicator.write_report(report_id=0, data=[0x01, 0x02])

        self.assertTrue(result)
        self.mock_hid_device.write.assert_called_once_with(b'\x01\x02')

    def test_write_report_hid_write_returns_zero_bytes(self, mock_logger):
        self.mock_hid_device.write.return_value = 0 # Simulate write returning 0 bytes

        result = self.communicator.write_report(report_id=0x01, data=[0x02, 0x03])

        self.assertFalse(result)
        mock_logger.warning.assert_called_with("HID write returned 0. This might indicate an issue with the device.")

    def test_write_report_hid_write_raises_exception(self, mock_logger):
        self.mock_hid_device.write.side_effect = Exception("HID Write Error")

        result = self.communicator.write_report(report_id=0x01, data=[0x02, 0x03])

        self.assertFalse(result)
        # Path decoding can be tricky if path is None or not bytes. Added defensive code in HIDCommunicator.
        # Let's assume mock_hid_device.path is set as b'/dev/mock_hid_path' in setUp.
        # The actual path string used in log will be its decoded version.
        decoded_path = self.mock_hid_device.path.decode('utf-8', 'replace')
        mock_logger.error.assert_called_with(f"HID write error on device {decoded_path}: HID Write Error")

    def test_read_report_success(self, mock_logger):
        expected_bytes = b'\x01\x02\x03'
        self.mock_hid_device.read.return_value = bytearray(expected_bytes) # hid.Device.read often returns bytearray

        result = self.communicator.read_report(report_length=3, timeout_ms=500)

        self.assertEqual(result, expected_bytes)
        self.mock_hid_device.read.assert_called_once_with(3, timeout_ms=500)
        mock_logger.debug.assert_any_call(f"HID read successful: {expected_bytes.hex()}")

    def test_read_report_no_data_returns_none(self, mock_logger):
        self.mock_hid_device.read.return_value = bytearray(b'') # Empty bytearray

        result = self.communicator.read_report(report_length=3)

        self.assertIsNone(result)
        mock_logger.warning.assert_called_with("No data received from HID read (length 3, timeout 1000ms).")

    def test_read_report_incomplete_data_returns_none(self, mock_logger):
        incomplete_bytes = b'\x01\x02'
        self.mock_hid_device.read.return_value = bytearray(incomplete_bytes)

        result = self.communicator.read_report(report_length=3)

        self.assertIsNone(result)
        mock_logger.warning.assert_called_with(f"Incomplete HID read. Expected 3 bytes, got 2: {incomplete_bytes.hex()}")

    def test_read_report_hid_read_raises_exception(self, mock_logger):
        self.mock_hid_device.read.side_effect = Exception("HID Read Error")

        result = self.communicator.read_report(report_length=3)

        self.assertIsNone(result)
        decoded_path = self.mock_hid_device.path.decode('utf-8', 'replace')
        mock_logger.error.assert_called_with(f"HID read error on device {decoded_path}: HID Read Error")

    def test_read_report_default_timeout(self, mock_logger):
        self.mock_hid_device.read.return_value = bytearray(b'\x01\x02\x03')
        self.communicator.read_report(report_length=3) # timeout_ms defaults to 1000
        self.mock_hid_device.read.assert_called_once_with(3, timeout_ms=1000)

    def test_read_report_none_timeout_uses_default(self, mock_logger):
        self.mock_hid_device.read.return_value = bytearray(b'\x01\x02\x03')
        self.communicator.read_report(report_length=3, timeout_ms=None)
        self.mock_hid_device.read.assert_called_once_with(3, timeout_ms=1000)
        mock_logger.warning.assert_called_with("read_report called with timeout_ms=None, defaulting to 1000ms to prevent potential indefinite block.")

if __name__ == "__main__":
    unittest.main()
