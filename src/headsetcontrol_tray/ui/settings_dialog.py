"""Provides the main settings dialog for the application."""
import logging

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QRadioButton,
    QSizePolicy,
    QSlider,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)

from headsetcontrol_tray import app_config
from headsetcontrol_tray import config_manager as cfg_mgr
from headsetcontrol_tray import headset_service as hs_svc

from .equalizer_editor_widget import EqualizerEditorWidget

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")


class SettingsDialog(QDialog):
    """Main settings dialog for the application."""

    eq_applied: Signal = Signal(str)
    settings_changed = Signal()

    def __init__(
        self,
        config_manager: cfg_mgr.ConfigManager,
        headset_service: hs_svc.HeadsetService,
        parent: QWidget | None = None,
    ) -> None:
        """
        Initializes the SettingsDialog.

        Args:
            config_manager: The application's ConfigManager instance.
            headset_service: The application's HeadsetService instance.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.config_manager = config_manager
        self.headset_service = headset_service

        self.setWindowTitle(f"{app_config.APP_NAME} - Settings")
        self.setMinimumWidth(600)

        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(15)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # --- ChatMix Group ---
        chatmix_main_groupbox = QGroupBox("ChatMix")
        chatmix_main_layout = QVBoxLayout(chatmix_main_groupbox)
        chatmix_main_layout.setSpacing(10)

        # --- ChatMix Visual Display (Slider as Bar) ---
        chatmix_visual_layout = QHBoxLayout()
        chatmix_visual_layout.setContentsMargins(5, 5, 5, 5)

        self.chat_label_indicator = QLabel("Chat")
        chatmix_visual_layout.addWidget(self.chat_label_indicator)

        self.chatmix_slider_bar = QSlider(Qt.Orientation.Horizontal)
        self.chatmix_slider_bar.setRange(0, 128)
        self.chatmix_slider_bar.setValue(64)  # Default to balanced visually
        self.chatmix_slider_bar.setEnabled(False)  # Non-interactive, for display only
        self.chatmix_slider_bar.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.chatmix_slider_bar.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.chatmix_slider_bar.setTickInterval(
            64,
        )  # Ticks at 0 (Chat), 64 (Balanced), 128 (Game)
        chatmix_visual_layout.addWidget(
            self.chatmix_slider_bar,
            1,
        )  # Give slider stretch factor

        self.game_label_indicator = QLabel("Game")
        chatmix_visual_layout.addWidget(self.game_label_indicator)

        chatmix_main_layout.addLayout(chatmix_visual_layout)
        # Add a small label below the slider for "Balanced" text
        balanced_label_indicator = QLabel("Balanced")
        balanced_label_indicator.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font_balanced = balanced_label_indicator.font()
        font_balanced.setPointSize(font_balanced.pointSize() - 1)
        balanced_label_indicator.setFont(font_balanced)
        chatmix_main_layout.addWidget(balanced_label_indicator)

        # --- Chat Application Identifiers (still part of ChatMix group) ---
        chat_apps_config_layout = QVBoxLayout()
        chat_apps_config_layout.setSpacing(5)
        chat_apps_config_layout.setContentsMargins(0, 10, 0, 0)  # Add some top margin

        chat_apps_label_info = QLabel(
            "Chat Application Identifiers (comma-separated, case-insensitive):",
        )
        chat_apps_label_info.setWordWrap(True)
        chat_apps_config_layout.addWidget(chat_apps_label_info)

        self.chat_apps_line_edit = QLineEdit()
        self.chat_apps_line_edit.setPlaceholderText("E.g., Discord, Teamspeak")
        chat_apps_config_layout.addWidget(self.chat_apps_line_edit)
        self.chat_apps_line_edit.editingFinished.connect(
            self._save_chat_app_identifiers,
        )

        chatmix_main_layout.addLayout(chat_apps_config_layout)
        main_layout.addWidget(chatmix_main_groupbox)

        # --- Sidetone Settings (Slider in GroupBox) ---
        sidetone_groupbox = QGroupBox("Sidetone Level")
        sidetone_group_layout = QVBoxLayout(sidetone_groupbox)

        sidetone_control_layout = QHBoxLayout()
        self.sidetone_slider = QSlider(Qt.Orientation.Horizontal)
        self.sidetone_slider.setRange(0, 128)
        self.sidetone_slider.setTickInterval(16)
        self.sidetone_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        sidetone_control_layout.addWidget(self.sidetone_slider)

        self.sidetone_value_label = QLabel("0")
        self.sidetone_value_label.setMinimumWidth(35)
        self.sidetone_value_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
        )
        sidetone_control_layout.addWidget(self.sidetone_value_label)
        sidetone_group_layout.addLayout(sidetone_control_layout)
        main_layout.addWidget(sidetone_groupbox)

        self.sidetone_slider.valueChanged.connect(
            self._on_sidetone_slider_value_changed,
        )
        self.sidetone_slider.sliderReleased.connect(self._apply_sidetone_setting)

        # --- Inactive Timeout Settings (in GroupBox) ---
        timeout_groupbox = QGroupBox("Inactive Timeout")
        timeout_group_layout = QHBoxLayout(timeout_groupbox)

        self.timeout_button_group = QButtonGroup(self)
        for text, minutes in app_config.INACTIVE_TIMEOUT_OPTIONS.items():
            rb = QRadioButton(text)
            timeout_group_layout.addWidget(rb)
            self.timeout_button_group.addButton(rb, minutes)
        timeout_group_layout.addStretch()
        main_layout.addWidget(timeout_groupbox)
        self.timeout_button_group.idClicked.connect(self._on_inactive_timeout_changed)

        # --- Equalizer Editor (in GroupBox) ---
        eq_groupbox = QGroupBox("Equalizer")
        eq_group_layout = QVBoxLayout(eq_groupbox)

        self.equalizer_widget = EqualizerEditorWidget(
            self.config_manager,
            self.headset_service,
            self,
        )
        self.equalizer_widget.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Preferred,
        )
        eq_group_layout.addWidget(self.equalizer_widget)
        main_layout.addWidget(eq_groupbox)

        self.equalizer_widget.eq_applied.connect(self.eq_applied)

        main_layout.addSpacerItem(
            QSpacerItem(
                20,
                10,
                QSizePolicy.Policy.Minimum,
                QSizePolicy.Policy.Expanding,
            ),
        )

        # --- Dialog buttons ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.button_box.rejected.connect(self.reject)
        self.button_box.accepted.connect(self.accept)
        main_layout.addWidget(self.button_box)

        self.setLayout(main_layout)
        self._load_initial_settings()

    def _load_initial_settings(self) -> None:
        current_sidetone = self.config_manager.get_last_sidetone_level()
        self.sidetone_slider.setValue(current_sidetone)
        self.sidetone_value_label.setText(str(current_sidetone))

        current_timeout = self.config_manager.get_last_inactive_timeout()
        timeout_button_to_check = self.timeout_button_group.button(current_timeout)
        if timeout_button_to_check:
            timeout_button_to_check.setChecked(True)

        chat_ids_list = self.config_manager.get_setting(
            "chat_app_identifiers",
            app_config.DEFAULT_CHAT_APP_IDENTIFIERS,
        )
        self.chat_apps_line_edit.setText(", ".join(chat_ids_list))

        self.refresh_chatmix_display()

    def get_chatmix_tooltip_string(self, chatmix_val: int | None) -> str:
        """Generates a descriptive tooltip string for a given ChatMix value."""
        if chatmix_val is None:
            return "ChatMix: N/A (Headset disconnected?)"
        percentage = round((chatmix_val / 128) * 100)
        if chatmix_val == 0:
            return f"ChatMix: Full Chat ({percentage}%)"
        if chatmix_val == 64:
            return f"ChatMix: Balanced ({percentage}%)"
        if chatmix_val == 128:
            return f"ChatMix: Full Game ({percentage}%)"
        return f"ChatMix: Custom Mix ({percentage}%)"

    def refresh_chatmix_display(self) -> None:
        """Refreshes the ChatMix visual display based on current headset value."""
        chatmix_val = self.headset_service.get_chatmix_value()
        tooltip_str = self.get_chatmix_tooltip_string(chatmix_val)
        self.chatmix_slider_bar.setToolTip(tooltip_str)

        if chatmix_val is not None:
            self.chatmix_slider_bar.setValue(chatmix_val)
            self.chatmix_slider_bar.setEnabled(
                False,
            )  # Ensure it remains visually disabled
        else:
            self.chatmix_slider_bar.setValue(
                64,
            )  # Default visual to balanced if no value
            self.chatmix_slider_bar.setEnabled(False)

    def _on_sidetone_slider_value_changed(self, value: int) -> None:
        self.sidetone_value_label.setText(str(value))

    def _apply_sidetone_setting(self) -> None:
        level = self.sidetone_slider.value()
        logger.info("SettingsDialog: Sidetone slider released at %s", level)
        if self.headset_service.set_sidetone_level(level):
            self.config_manager.set_last_sidetone_level(level)
            self.settings_changed.emit()
        else:
            QMessageBox.warning(
                self,
                "Error",
                "Failed to set sidetone level. Is the headset connected?",
            )
            current_sidetone = self.config_manager.get_last_sidetone_level()
            self.sidetone_slider.setValue(current_sidetone)
            self.sidetone_value_label.setText(str(current_sidetone))

    def _on_inactive_timeout_changed(self, minutes_id: int) -> None:
        logger.info("SettingsDialog: Inactive timeout changed to ID %s", minutes_id)
        if self.headset_service.set_inactive_timeout(minutes_id):
            self.config_manager.set_last_inactive_timeout(minutes_id)
            self.settings_changed.emit()
        else:
            QMessageBox.warning(
                self,
                "Error",
                "Failed to set inactive timeout. Is the headset connected?",
            )
            self._load_initial_settings()

    def showEvent(self, event: QShowEvent) -> None:
        """Reloads settings and refreshes view when the dialog is shown."""
        super().showEvent(event)
        self._load_initial_settings()
        self.equalizer_widget.refresh_view()

    def _save_chat_app_identifiers(self) -> None:
        current_text = self.chat_apps_line_edit.text().strip()
        new_identifiers = [
            ident.strip() for ident in current_text.split(",") if ident.strip()
        ]

        old_identifiers = self.config_manager.get_setting(
            "chat_app_identifiers",
            app_config.DEFAULT_CHAT_APP_IDENTIFIERS,
        )

        if set(new_identifiers) != set(old_identifiers):
            self.config_manager.set_setting("chat_app_identifiers", new_identifiers)
            logger.info("Chat application identifiers updated to: %s", new_identifiers)
            self.settings_changed.emit()
