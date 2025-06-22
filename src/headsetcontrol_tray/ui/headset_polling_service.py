"""Manages periodic polling of headset status and emits updates."""

import logging

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from headsetcontrol_tray import app_config
from headsetcontrol_tray import headset_service as hs_svc

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")

# Polling intervals (could be centralized in app_config if used elsewhere)
NORMAL_REFRESH_INTERVAL_MS = 1000
FAST_REFRESH_INTERVAL_MS = 100
FAST_POLL_NO_CHANGE_THRESHOLD = 3  # Num fast polls with no change before normal
BATTERY_LEVEL_FULL=100

class HeadsetPollingService(QObject):
    """Periodically polls HeadsetService for status updates and emits them.

    Also manages adaptive polling intervals.
    """

    status_updated = Signal(dict)  # Emits a dictionary with the latest status

    # Constants for status dict keys (to be used by consumers)
    KEY_IS_CONNECTED = "is_connected"
    KEY_BATTERY_LEVEL = "battery_level"
    KEY_BATTERY_STATUS_TEXT = "battery_status_text"  # e.g. "BATTERY_CHARGING"
    KEY_CHATMIX_VALUE = "chatmix_value"
    KEY_CONNECTION_STATE_CHANGED = "connection_state_changed"
    KEY_DATA_CHANGED_WHILE_CONNECTED = "data_changed_while_connected"

    def __init__(
        self, headset_service: hs_svc.HeadsetService, parent: QObject | None = None
    ) -> None:
        """Initializes the HeadsetPollingService.

        Args:
            headset_service: The headset service instance.
            parent: Optional QObject parent.
        """
        super().__init__(parent)
        self.headset_service = headset_service

        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self._poll_status)

        # Internal state for polling logic
        self._is_currently_connected = False  # Tracks connection state known by this poller
        self._last_known_battery_level: int | None = None
        self._last_known_battery_status_text: str | None = None
        self._last_known_chatmix_value: int | None = None

        self._fast_poll_active = False
        self._fast_poll_no_change_counter = 0

        self._is_first_poll = True

    def start(self) -> None:
        """Starts the polling timer with the normal interval."""
        if not self.refresh_timer.isActive():
            self._is_first_poll = True  # Reset for initial full update
            self.refresh_timer.setInterval(NORMAL_REFRESH_INTERVAL_MS)
            self.refresh_timer.start()
            logger.info(
                "HeadsetPollingService started with interval %sms.",
                NORMAL_REFRESH_INTERVAL_MS,
            )
            self._poll_status()  # Initial immediate poll

    def stop(self) -> None:
        """Stops the polling timer."""
        if self.refresh_timer.isActive():
            self.refresh_timer.stop()
            logger.info("HeadsetPollingService stopped.")

    @Slot()  # Ensure it's recognized as a slot for QTimer
    def _poll_status(self) -> None:
        """
        Polls the headset service for status, processes it, and emits updates.
        Also manages the adaptive polling interval.
        """
        logger.debug(
            "Polling headset status (Current Interval: %sms)...",
            self.refresh_timer.interval(),
        )

        previous_connection_state = self._is_currently_connected
        current_is_connected = self.headset_service.is_device_connected()
        self._is_currently_connected = current_is_connected
        connection_state_changed = current_is_connected != previous_connection_state

        if connection_state_changed:
            logger.info(
                "PollingService: Headset connection state changed to %s.",
                "connected" if current_is_connected else "disconnected",
            )

        current_battery_level: int | None = None
        current_battery_status_text: str | None = None  # e.g. "BATTERY_CHARGING", "BATTERY_FULL", "BATTERY_AVAILABLE"
        current_chatmix_value: int | None = None
        data_changed_while_connected = False

        if not current_is_connected:
            current_battery_level = None
            current_battery_status_text = None  # Or a specific "DISCONNECTED" status
            current_chatmix_value = None
            # Check if there was a change from a connected state with data
            if self._last_known_battery_level is not None or self._last_known_chatmix_value is not None:
                data_changed_while_connected = True  # Data effectively "changed" to None
        else:
            current_battery_level = self.headset_service.get_battery_level()
            is_charging = self.headset_service.is_charging()

            if is_charging:
                current_battery_status_text = "BATTERY_CHARGING"
            elif current_battery_level == BATTERY_LEVEL_FULL:
                current_battery_status_text = "BATTERY_FULL"
            elif current_battery_level is not None:
                current_battery_status_text = "BATTERY_AVAILABLE"
            else:
                current_battery_status_text = "BATTERY_UNAVAILABLE"

            current_chatmix_value = self.headset_service.get_chatmix_value()

            if (
                current_battery_level != self._last_known_battery_level
                or current_battery_status_text != self._last_known_battery_status_text
                or current_chatmix_value != self._last_known_chatmix_value
            ):
                data_changed_while_connected = True

        # Always emit on first poll or if state changed
        should_emit = self._is_first_poll or connection_state_changed or data_changed_while_connected

        if should_emit:
            status_payload = {
                self.KEY_IS_CONNECTED: current_is_connected,
                self.KEY_BATTERY_LEVEL: current_battery_level,
                self.KEY_BATTERY_STATUS_TEXT: current_battery_status_text,
                self.KEY_CHATMIX_VALUE: current_chatmix_value,
                self.KEY_CONNECTION_STATE_CHANGED: connection_state_changed,
                self.KEY_DATA_CHANGED_WHILE_CONNECTED: data_changed_while_connected,
            }
            logger.debug("Emitting status_updated: %s", status_payload)
            self.status_updated.emit(status_payload)
            self._is_first_poll = False  # Clear after first emission

        # Update last known states for the next cycle
        self._last_known_battery_level = current_battery_level
        self._last_known_battery_status_text = current_battery_status_text
        self._last_known_chatmix_value = current_chatmix_value

        self._manage_polling_interval(
            current_is_connected=current_is_connected,
            data_changed_this_cycle=data_changed_while_connected,  # Use the more specific flag
            connection_state_changed_this_cycle=connection_state_changed,
        )
        logger.debug("Polling complete.")

    def _manage_polling_interval(
        self,
        *,
        current_is_connected: bool,
        data_changed_this_cycle: bool,
        connection_state_changed_this_cycle: bool,
    ) -> None:
        """Manages the polling interval based on connection and data changes."""
        if not current_is_connected:
            if self.refresh_timer.interval() != NORMAL_REFRESH_INTERVAL_MS:
                self.refresh_timer.setInterval(NORMAL_REFRESH_INTERVAL_MS)
                logger.debug(
                    "Device disconnected. Switched to normal refresh interval (%sms).",
                    NORMAL_REFRESH_INTERVAL_MS,
                )
            self._fast_poll_active = False
            self._fast_poll_no_change_counter = 0
        elif self._fast_poll_active:
            if not data_changed_this_cycle:  # If connected and fast polling, check for data changes
                self._fast_poll_no_change_counter += 1
                if self._fast_poll_no_change_counter >= FAST_POLL_NO_CHANGE_THRESHOLD:
                    self.refresh_timer.setInterval(NORMAL_REFRESH_INTERVAL_MS)
                    self._fast_poll_active = False
                    self._fast_poll_no_change_counter = 0
                    logger.debug(
                        "No change threshold reached on fast poll. Switched to normal interval (%sms).",
                        NORMAL_REFRESH_INTERVAL_MS,
                    )
            else:  # Data changed during fast poll
                self._fast_poll_no_change_counter = 0  # Reset counter
        # Switch to fast poll if connection state changed OR if data changed while connected
        elif connection_state_changed_this_cycle or data_changed_this_cycle:
            if self.refresh_timer.interval() != FAST_REFRESH_INTERVAL_MS:
                self.refresh_timer.setInterval(FAST_REFRESH_INTERVAL_MS)
                logger.debug(
                    "State change detected (connection or data). Switched to fast refresh interval (%sms).",
                    FAST_REFRESH_INTERVAL_MS,
                )
            self._fast_poll_active = True
            self._fast_poll_no_change_counter = 0
        # else: currently connected, not fast polling, and no data change -> keep normal interval
