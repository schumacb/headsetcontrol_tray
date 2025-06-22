"""Unit tests for the HeadsetPollingService class."""

import unittest
from unittest.mock import MagicMock, patch  # Added call

from headsetcontrol_tray.ui.headset_polling_service import (
    BATTERY_LEVEL_FULL,
    FAST_POLL_NO_CHANGE_THRESHOLD,
    FAST_REFRESH_INTERVAL_MS,
    NORMAL_REFRESH_INTERVAL_MS,
    HeadsetPollingService,
)


class TestHeadsetPollingService(unittest.TestCase):
    """Test suite for the HeadsetPollingService."""

    @patch("headsetcontrol_tray.ui.headset_polling_service.QTimer")
    def setUp(self, mock_qtimer_class) -> None:
        self.mock_headset_service = MagicMock()
        self.mock_qtimer_instance = mock_qtimer_class.return_value

        self.polling_service = HeadsetPollingService(headset_service=self.mock_headset_service)
        self.polling_service.status_updated = MagicMock()  # Mock the signal

    def test_initialization(self) -> None:
        """Test service initialization and QTimer setup."""
        self.mock_qtimer_instance.timeout.connect.assert_called_once_with(self.polling_service._poll_status)
        assert not self.polling_service._fast_poll_active
        assert self.polling_service._fast_poll_no_change_counter == 0

    def test_start_polling(self) -> None:
        """Test starting the polling service."""
        self.polling_service.start()
        self.mock_qtimer_instance.setInterval.assert_called_once_with(NORMAL_REFRESH_INTERVAL_MS)
        self.mock_qtimer_instance.start.assert_called_once()
        # _poll_status should be called once immediately by start()
        assert self.polling_service.status_updated.emit.call_count == 1

    def test_stop_polling(self) -> None:
        """Test stopping the polling service."""
        self.mock_qtimer_instance.isActive.return_value = True
        self.polling_service.stop()
        self.mock_qtimer_instance.stop.assert_called_once()

    def test_poll_status_device_disconnected(self) -> None:
        """Test polling when device is disconnected."""
        self.mock_headset_service.is_device_connected.return_value = False
        self.polling_service._is_first_poll = True  # Ensure emit on first
        self.polling_service._poll_status()

        expected_payload = {
            HeadsetPollingService.KEY_IS_CONNECTED: False,
            HeadsetPollingService.KEY_BATTERY_LEVEL: None,
            HeadsetPollingService.KEY_BATTERY_STATUS_TEXT: None,
            HeadsetPollingService.KEY_CHATMIX_VALUE: None,
            HeadsetPollingService.KEY_CONNECTION_STATE_CHANGED: False,  # Assuming starts disconnected
            HeadsetPollingService.KEY_DATA_CHANGED_WHILE_CONNECTED: False,
        }
        self.polling_service.status_updated.emit.assert_called_with(expected_payload)
        assert self.mock_qtimer_instance.setInterval.call_count == 0  # Should remain normal

    def test_poll_status_device_connected_no_change(self) -> None:
        """Test polling when device is connected and data does not change."""
        self.mock_headset_service.is_device_connected.return_value = True
        self.mock_headset_service.get_battery_level.return_value = 70
        self.mock_headset_service.is_charging.return_value = False
        self.mock_headset_service.get_chatmix_value.return_value = 64

        # Initial poll to set the state
        self.polling_service._is_first_poll = True
        self.polling_service._poll_status()
        self.polling_service.status_updated.emit.reset_mock()
        self.polling_service._is_first_poll = False  # Subsequent polls

        # Second poll, no data change
        self.polling_service._poll_status()
        # Should not emit if no change and not first poll
        self.polling_service.status_updated.emit.assert_not_called()

    def test_poll_status_device_connected_data_changes(self) -> None:
        """Test polling when device is connected and data changes."""
        self.mock_headset_service.is_device_connected.return_value = True
        self.mock_headset_service.get_battery_level.return_value = 70
        self.mock_headset_service.is_charging.return_value = False
        self.mock_headset_service.get_chatmix_value.return_value = 64

        self.polling_service._is_first_poll = True
        self.polling_service._poll_status()  # Initial poll
        self.polling_service.status_updated.emit.reset_mock()
        self.polling_service._is_first_poll = False

        # Change data for the next poll
        self.mock_headset_service.get_battery_level.return_value = 60
        self.polling_service._poll_status()

        expected_payload = {
            HeadsetPollingService.KEY_IS_CONNECTED: True,
            HeadsetPollingService.KEY_BATTERY_LEVEL: 60,
            HeadsetPollingService.KEY_BATTERY_STATUS_TEXT: "BATTERY_AVAILABLE",
            HeadsetPollingService.KEY_CHATMIX_VALUE: 64,
            HeadsetPollingService.KEY_CONNECTION_STATE_CHANGED: False,
            HeadsetPollingService.KEY_DATA_CHANGED_WHILE_CONNECTED: True,
        }
        self.polling_service.status_updated.emit.assert_called_with(expected_payload)
        # Should switch to fast polling
        self.mock_qtimer_instance.setInterval.assert_called_with(FAST_REFRESH_INTERVAL_MS)

    def test_poll_status_connection_state_changes_to_connected(self) -> None:
        """Test polling when device changes from disconnected to connected."""
        # Initial state: disconnected
        self.polling_service._is_currently_connected = False
        self.mock_headset_service.is_device_connected.return_value = False
        self.polling_service._is_first_poll = True
        self.polling_service._poll_status()
        self.polling_service.status_updated.emit.reset_mock()
        self.polling_service._is_first_poll = False

        # Next poll: connected
        self.mock_headset_service.is_device_connected.return_value = True
        self.mock_headset_service.get_battery_level.return_value = 80
        self.mock_headset_service.is_charging.return_value = True
        self.mock_headset_service.get_chatmix_value.return_value = 32
        self.polling_service._poll_status()

        expected_payload = {
            HeadsetPollingService.KEY_IS_CONNECTED: True,
            HeadsetPollingService.KEY_BATTERY_LEVEL: 80,
            HeadsetPollingService.KEY_BATTERY_STATUS_TEXT: "BATTERY_CHARGING",
            HeadsetPollingService.KEY_CHATMIX_VALUE: 32,
            HeadsetPollingService.KEY_CONNECTION_STATE_CHANGED: True,
            HeadsetPollingService.KEY_DATA_CHANGED_WHILE_CONNECTED: True,  # Data also "changed" from None
        }
        self.polling_service.status_updated.emit.assert_called_with(expected_payload)
        self.mock_qtimer_instance.setInterval.assert_called_with(FAST_REFRESH_INTERVAL_MS)

    def test_adaptive_polling_switches_to_normal(self) -> None:
        """Test adaptive polling switches back to normal after no changes."""
        # Start connected, trigger fast poll
        self.mock_headset_service.is_device_connected.return_value = True
        self.mock_headset_service.get_battery_level.return_value = 70
        self.mock_headset_service.is_charging.return_value = False
        self.mock_headset_service.get_chatmix_value.return_value = 64
        self.polling_service._is_first_poll = True
        self.polling_service._poll_status()  # Initial call, sets data
        # Assume connection state changed or data changed, so it's fast polling
        self.polling_service._fast_poll_active = True
        self.mock_qtimer_instance.setInterval(FAST_REFRESH_INTERVAL_MS)
        self.polling_service.status_updated.emit.reset_mock()
        self.mock_qtimer_instance.setInterval.reset_mock()
        self.polling_service._is_first_poll = False

        # Simulate no changes for FAST_POLL_NO_CHANGE_THRESHOLD times
        for i in range(FAST_POLL_NO_CHANGE_THRESHOLD):
            self.polling_service._poll_status()
            self.polling_service.status_updated.emit.assert_not_called()  # No emit if no data change
            if i < FAST_POLL_NO_CHANGE_THRESHOLD - 1:
                self.mock_qtimer_instance.setInterval.assert_not_called()  # Should not switch yet

        # On the threshold poll, it should switch back to normal
        self.mock_qtimer_instance.setInterval.assert_called_with(NORMAL_REFRESH_INTERVAL_MS)
        assert not self.polling_service._fast_poll_active

    def test_battery_status_text_logic(self) -> None:
        """Test the logic for determining battery_status_text."""
        self.mock_headset_service.is_device_connected.return_value = True
        self.polling_service._is_first_poll = True

        # Charging
        self.mock_headset_service.get_battery_level.return_value = 50
        self.mock_headset_service.is_charging.return_value = True
        self.polling_service._poll_status()
        self.polling_service.status_updated.emit.assert_called_with(
            unittest.mock.ANY,  # Previous tests cover full payload
        )
        assert self.polling_service._last_known_battery_status_text == "BATTERY_CHARGING"
        self.polling_service.status_updated.emit.reset_mock()
        self.polling_service._is_first_poll = False

        # Full (and not charging, though is_charging=False is implicit if not BATTERY_CHARGING)
        self.mock_headset_service.get_battery_level.return_value = BATTERY_LEVEL_FULL
        self.mock_headset_service.is_charging.return_value = False
        self.polling_service._poll_status()
        self.polling_service.status_updated.emit.assert_called_with(unittest.mock.ANY)
        assert self.polling_service._last_known_battery_status_text == "BATTERY_FULL"
        self.polling_service.status_updated.emit.reset_mock()

        # Available
        self.mock_headset_service.get_battery_level.return_value = 70  # Not full
        self.mock_headset_service.is_charging.return_value = False
        self.polling_service._poll_status()
        self.polling_service.status_updated.emit.assert_called_with(unittest.mock.ANY)
        assert self.polling_service._last_known_battery_status_text == "BATTERY_AVAILABLE"
        self.polling_service.status_updated.emit.reset_mock()

        self.mock_headset_service.get_battery_level.return_value = None
        self.mock_headset_service.is_charging.return_value = False  # Doesn't matter if level is None
        self.polling_service._poll_status() # pylint: disable=protected-access
        self.polling_service.status_updated.emit.assert_called_with(unittest.mock.ANY)
        assert self.polling_service._last_known_battery_status_text == "BATTERY_UNAVAILABLE"


if __name__ == "__main__":
    unittest.main()
