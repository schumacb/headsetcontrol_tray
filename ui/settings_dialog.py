from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QPushButton, QHBoxLayout, QDialogButtonBox,
    QRadioButton, QLabel, QButtonGroup, QSizePolicy, QMessageBox, QSlider, QSpacerItem,
    QGroupBox
)
from PySide6.QtCore import Signal, Qt
import logging
from typing import Dict, Optional

from .equalizer_editor_widget import EqualizerEditorWidget
from .. import config_manager as cfg_mgr
from .. import headset_service as hs_svc
from .. import app_config

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")


class SettingsDialog(QDialog):
    """Main settings dialog for the application."""
    eq_applied: Signal = Signal(str) 
    settings_changed = Signal()

    def __init__(self, config_manager: cfg_mgr.ConfigManager, headset_service: hs_svc.HeadsetService, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.headset_service = headset_service

        self.setWindowTitle(f"{app_config.APP_NAME} - Settings")
        self.setMinimumWidth(600)

        main_layout = QVBoxLayout(self)

        # --- ChatMix Display ---
        self.chatmix_label = QLabel("ChatMix: N/A")
        self.chatmix_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        font = self.chatmix_label.font()
        font.setPointSize(font.pointSize() + 1)
        self.chatmix_label.setFont(font)
        main_layout.addWidget(self.chatmix_label)

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
        self.sidetone_value_label.setMinimumWidth(30) 
        self.sidetone_value_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        sidetone_control_layout.addWidget(self.sidetone_value_label)
        sidetone_group_layout.addLayout(sidetone_control_layout)
        main_layout.addWidget(sidetone_groupbox)
        
        self.sidetone_slider.valueChanged.connect(self._on_sidetone_slider_value_changed)
        self.sidetone_slider.sliderReleased.connect(self._apply_sidetone_setting)


        # --- Inactive Timeout Settings (in GroupBox) ---
        timeout_groupbox = QGroupBox("Inactive Timeout")
        timeout_group_layout = QHBoxLayout(timeout_groupbox)
        
        self.timeout_button_group = QButtonGroup(self)
        for idx, (text, minutes) in enumerate(app_config.INACTIVE_TIMEOUT_OPTIONS.items()):
            rb = QRadioButton(text)
            timeout_group_layout.addWidget(rb)
            self.timeout_button_group.addButton(rb, minutes)
        timeout_group_layout.addStretch() 
        main_layout.addWidget(timeout_groupbox)
        self.timeout_button_group.idClicked.connect(self._on_inactive_timeout_changed)

        # --- Equalizer Editor (in GroupBox) ---
        eq_groupbox = QGroupBox("Equalizer")
        eq_group_layout = QVBoxLayout(eq_groupbox)

        self.equalizer_widget = EqualizerEditorWidget(self.config_manager, self.headset_service, self)
        self.equalizer_widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        eq_group_layout.addWidget(self.equalizer_widget)
        main_layout.addWidget(eq_groupbox)
        
        self.equalizer_widget.eq_applied.connect(self.eq_applied) 

        main_layout.addSpacerItem(QSpacerItem(20, 10, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))

        # --- Dialog buttons ---
        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box)

        self.setLayout(main_layout)
        self._load_initial_settings()

    def _load_initial_settings(self):
        current_sidetone = self.config_manager.get_last_sidetone_level()
        self.sidetone_slider.setValue(current_sidetone)
        self.sidetone_value_label.setText(str(current_sidetone))
        
        current_timeout = self.config_manager.get_last_inactive_timeout()
        timeout_button_to_check = self.timeout_button_group.button(current_timeout)
        if timeout_button_to_check:
            timeout_button_to_check.setChecked(True)
        
        self.refresh_chatmix_display()

    def get_chatmix_display_string(self, chatmix_val: Optional[int]) -> str:
        if chatmix_val is None: return "N/A"
        percentage = round((chatmix_val / 128) * 100)
        if chatmix_val == 0: return f"Full Chat ({percentage}%)"
        elif chatmix_val == 64: return f"Balanced ({percentage}%)"
        elif chatmix_val == 128: return f"Full Game ({percentage}%)"
        else: return f"{chatmix_val} ({percentage}%)"

    def refresh_chatmix_display(self):
        chatmix_val = self.headset_service.get_chatmix_value()
        display_str = self.get_chatmix_display_string(chatmix_val)
        self.chatmix_label.setText(f"ChatMix: {display_str}")

    def _on_sidetone_slider_value_changed(self, value: int):
        self.sidetone_value_label.setText(str(value))

    def _apply_sidetone_setting(self):
        level = self.sidetone_slider.value()
        logger.info(f"SettingsDialog: Sidetone slider released at {level}")
        if self.headset_service.set_sidetone_level(level):
            self.config_manager.set_last_sidetone_level(level)
            self.settings_changed.emit()
        else:
            QMessageBox.warning(self, "Error", "Failed to set sidetone level.")
            current_sidetone = self.config_manager.get_last_sidetone_level()
            self.sidetone_slider.setValue(current_sidetone) # Revert slider
            self.sidetone_value_label.setText(str(current_sidetone)) # Revert label

    def _on_inactive_timeout_changed(self, minutes_id: int):
        logger.info(f"SettingsDialog: Inactive timeout changed to ID {minutes_id}")
        if self.headset_service.set_inactive_timeout(minutes_id):
            self.config_manager.set_last_inactive_timeout(minutes_id)
            self.settings_changed.emit()
        else:
            QMessageBox.warning(self, "Error", "Failed to set inactive timeout.")
            self._load_initial_settings() # Revert radio button selection

    def showEvent(self, event):
        super().showEvent(event)
        self._load_initial_settings() 
        self.equalizer_widget.refresh_view()