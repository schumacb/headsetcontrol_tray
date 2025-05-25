# steelseries_tray/ui/equalizer_editor_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSlider, QLabel, QPushButton,
    QComboBox, QMessageBox, QGridLayout, QInputDialog
)
from PySide6.QtCore import Qt, Signal, QTimer
from typing import List, Optional, Dict

from .. import config_manager as cfg_mgr
from .. import headset_service as hs_svc
from .. import app_config
import logging 

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")


class EqualizerEditorDialog(QDialog):
    """Dialog for editing and managing custom equalizer curves."""
    eq_applied = Signal(str) # Emits name of applied custom curve

    def __init__(self, config_manager: cfg_mgr.ConfigManager, headset_service: hs_svc.HeadsetService, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.headset_service = headset_service

        self.setWindowTitle("Equalizer Editor")
        self.setMinimumWidth(500)

        self.sliders: List[QSlider] = []
        self.slider_labels: List[QLabel] = []
        
        self._current_selected_curve_name_in_combo: Optional[str] = None
        self._current_selected_curve_original_name: Optional[str] = None
        self._current_selected_curve_saved_values: List[int] = [0]*10
        self._sliders_have_unsaved_changes: bool = False

        self._slider_apply_debounce_timer = QTimer(self)
        self._slider_apply_debounce_timer.setSingleShot(True)
        self._slider_apply_debounce_timer.setInterval(250) 
        self._slider_apply_debounce_timer.timeout.connect(self._apply_sliders_to_headset_and_check_changes)


        self._init_ui()
        self._load_curve_names_to_combo()
        self._select_initial_curve_and_load_values() 
        self._update_button_states()


    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        manage_layout = QHBoxLayout()
        self.curve_combo = QComboBox()
        self.curve_combo.setMinimumWidth(200)
        self.curve_combo.currentTextChanged.connect(self._on_curve_selected_in_combo) 
        manage_layout.addWidget(QLabel("Curve:"))
        manage_layout.addWidget(self.curve_combo)

        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._save_curve)
        manage_layout.addWidget(self.save_button)

        self.save_as_button = QPushButton("Save As...")
        self.save_as_button.clicked.connect(self._save_curve_as)
        manage_layout.addWidget(self.save_as_button)
        
        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self._delete_curve)
        manage_layout.addWidget(self.delete_button)
        manage_layout.addStretch()
        main_layout.addLayout(manage_layout)

        slider_layout = QGridLayout()
        eq_bands_khz = ["31", "62", "125", "250", "500", "1k", "2k", "4k", "8k", "16k"]
        for i in range(10):
            slider_vbox = QVBoxLayout()
            
            lbl_freq = QLabel(eq_bands_khz[i])
            lbl_freq.setAlignment(Qt.AlignmentFlag.AlignCenter)
            slider_vbox.addWidget(lbl_freq)

            slider = QSlider(Qt.Orientation.Vertical)
            slider.setRange(-10, 10)
            slider.setValue(0)
            slider.setTickInterval(1)
            slider.setTickPosition(QSlider.TickPosition.TicksRight)
            slider.valueChanged.connect(self._on_slider_value_changed) 
            self.sliders.append(slider)
            slider_vbox.addWidget(slider, alignment=Qt.AlignmentFlag.AlignCenter)

            label = QLabel("0 dB")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.slider_labels.append(label)
            slider_vbox.addWidget(label)
            
            slider_layout.addLayout(slider_vbox, 0, i)
        main_layout.addLayout(slider_layout)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.discard_button = QPushButton("Discard Changes")
        self.discard_button.clicked.connect(self._discard_changes)
        button_layout.addWidget(self.discard_button)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)
        main_layout.addLayout(button_layout)

    def _update_slider_label(self, index: int, value: int):
        self.slider_labels[index].setText(f"{value} dB")

    def _on_slider_value_changed(self, value: int):
        sender_slider = self.sender()
        if sender_slider in self.sliders:
            idx = self.sliders.index(sender_slider)
            self._update_slider_label(idx, value)
        
        self._slider_apply_debounce_timer.start()

    def _apply_sliders_to_headset_and_check_changes(self):
        """Applies current slider values to headset and then checks for unsaved changes."""
        current_values = self._get_slider_values()
        logger.debug(f"Applying sliders to headset: {current_values}")
        if self.headset_service.set_eq_values(current_values):
            if self._current_selected_curve_original_name:
                 self.eq_applied.emit(self._current_selected_curve_original_name)
        else:
            QMessageBox.warning(self, "EQ Error", "Failed to apply EQ settings to headset.")
        self._check_for_unsaved_changes()


    def _check_for_unsaved_changes(self):
        """Checks if current slider values differ from the saved state of the selected curve."""
        if not self._current_selected_curve_original_name: 
            self._sliders_have_unsaved_changes = False 
        else:
            current_slider_vals = self._get_slider_values()
            self._sliders_have_unsaved_changes = (current_slider_vals != self._current_selected_curve_saved_values)
        
        logger.debug(f"Checked for unsaved changes for '{self._current_selected_curve_original_name}': {self._sliders_have_unsaved_changes}")
        self._update_ui_for_unsaved_changes_status()

    def _update_ui_for_unsaved_changes_status(self):
        """Updates combo box item text and button states based on unsaved changes."""
        self.curve_combo.blockSignals(True)
        current_idx = self.curve_combo.currentIndex()
        if current_idx != -1 and self._current_selected_curve_original_name:
            text_to_display = self._current_selected_curve_original_name
            if self._sliders_have_unsaved_changes:
                text_to_display += "*"
            
            if self.curve_combo.itemText(current_idx) != text_to_display:
                 self.curve_combo.setItemText(current_idx, text_to_display)
        self.curve_combo.blockSignals(False)
        self._update_button_states()

    def _update_button_states(self):
        self.discard_button.setEnabled(self._sliders_have_unsaved_changes)
        can_save_existing = self._sliders_have_unsaved_changes and bool(self._current_selected_curve_original_name)
        self.save_button.setEnabled(can_save_existing)
        
        can_delete = False
        if self._current_selected_curve_original_name:
            if self._current_selected_curve_original_name not in app_config.DEFAULT_EQ_CURVES:
                can_delete = True
        self.delete_button.setEnabled(can_delete)


    def _load_curve_names_to_combo(self):
        self.curve_combo.blockSignals(True)
        self.curve_combo.clear()
        curves = self.config_manager.get_all_custom_eq_curves()
        sorted_names = sorted(curves.keys(), key=lambda x: (x not in app_config.DEFAULT_EQ_CURVES, x.lower()))
        for name in sorted_names:
            self.curve_combo.addItem(name)
        self.curve_combo.blockSignals(False)

    def _select_initial_curve_and_load_values(self):
        """Selects the initial curve in the combobox and explicitly loads its values to sliders."""
        logger.debug("Selecting initial curve and loading values for EQ Editor dialog.")
        
        # Primary: Use the last custom EQ curve name stored in config.
        last_custom_name = self.config_manager.get_last_custom_eq_curve_name()
        logger.debug(f"Retrieved last_custom_name from config: '{last_custom_name}'")

        target_name_to_select = None

        if last_custom_name and self.curve_combo.findText(last_custom_name) != -1:
            target_name_to_select = last_custom_name
            logger.debug(f"Using last_custom_name '{target_name_to_select}' as initial target.")
        elif self.curve_combo.count() > 0: # Fallback if last_custom_name is not valid or not found
            flat_idx = self.curve_combo.findText("Flat")
            if flat_idx != -1:
                target_name_to_select = "Flat"
                logger.debug(f"Fallback: last_custom_name '{last_custom_name}' invalid or not in combo. Using 'Flat'.")
            else: 
                target_name_to_select = self.curve_combo.itemText(0)
                logger.debug(f"Fallback: Using first item in combo: '{target_name_to_select}'. ('Flat' not found, last_custom_name invalid).")
        else:
            logger.warning("No curves available in combobox. Cannot select an initial curve.")
            # Set sliders to flat and imply this is a "new unsaved" state if desired
            self._set_sliders_and_apply([0]*10)
            self._current_selected_curve_original_name = None 
            self._current_selected_curve_name_in_combo = None
            self._current_selected_curve_saved_values = [0]*10
            self._sliders_have_unsaved_changes = True # New from scratch implies changes
            self._update_ui_for_unsaved_changes_status()
            return

        idx_to_select_in_combo = self.curve_combo.findText(target_name_to_select)

        if idx_to_select_in_combo != -1:
            logger.debug(f"Setting combo index to {idx_to_select_in_combo} ('{target_name_to_select}') and loading its values.")
            self.curve_combo.blockSignals(True)
            self.curve_combo.setCurrentIndex(idx_to_select_in_combo)
            self.curve_combo.blockSignals(False)
            
            self._current_selected_curve_name_in_combo = target_name_to_select 
            self._current_selected_curve_original_name = target_name_to_select.rstrip('*')
            
            logger.debug(f"Loading values for initial curve: '{self._current_selected_curve_original_name}'")
            values = self.config_manager.get_custom_eq_curve(self._current_selected_curve_original_name)
            
            if values:
                logger.debug(f"Values found for '{self._current_selected_curve_original_name}': {values}")
                self._current_selected_curve_saved_values = list(values)
                self._set_sliders_and_apply(list(values)) 
            else: 
                logger.warning(f"No values found for '{self._current_selected_curve_original_name}', defaulting to flat.")
                self._current_selected_curve_saved_values = [0]*10
                self._set_sliders_and_apply([0]*10)
            
            self._sliders_have_unsaved_changes = False 
            self._update_ui_for_unsaved_changes_status() 
            
        else: # Should not be reached if target_name_to_select was derived from existing combo items
            logger.error(f"Could not find target_name_to_select '{target_name_to_select}' in combobox after decision. This is unexpected.")
            if self.curve_combo.count() > 0: # Safe fallback
                self.curve_combo.setCurrentIndex(0)
                # Triggering currentTextChanged here should load the first item.
            else: # No curves at all if this branch is hit (very edge case)
                self._set_sliders_and_apply([0]*10)
                self._current_selected_curve_original_name = None
                self._current_selected_curve_name_in_combo = None
                self._current_selected_curve_saved_values = [0]*10
                self._sliders_have_unsaved_changes = True
                self._update_ui_for_unsaved_changes_status()


    def _on_curve_selected_in_combo(self, new_text_in_combo: str):
        """Handles when the user changes the selection in the QComboBox."""
        logger.debug(f"_on_curve_selected_in_combo: Text changed to '{new_text_in_combo}'")
        self.curve_combo.blockSignals(True) 
        
        original_name = new_text_in_combo.rstrip('*')
        self._current_selected_curve_name_in_combo = new_text_in_combo 
        self._current_selected_curve_original_name = original_name

        logger.debug(f"Loading values for user-selected curve: '{original_name}'")
        values = self.config_manager.get_custom_eq_curve(original_name)
        if values:
            logger.debug(f"Values found: {values}")
            self._current_selected_curve_saved_values = list(values) 
            self._set_sliders_and_apply(list(values)) 
        else: 
            logger.warning(f"No values found for '{original_name}' on user selection, defaulting to flat.")
            self._current_selected_curve_saved_values = [0]*10
            self._set_sliders_and_apply([0]*10) 
            
        self._sliders_have_unsaved_changes = False 
        self._update_ui_for_unsaved_changes_status() 
        self.curve_combo.blockSignals(False)


    def _set_sliders_and_apply(self, values: List[int]):
        """Sets slider positions and applies these values to the headset."""
        logger.debug(f"Setting sliders to visuals: {values} and applying to headset.")
        for i, value in enumerate(values):
            self.sliders[i].blockSignals(True)
            self.sliders[i].setValue(value)
            self.sliders[i].blockSignals(False)
            self._update_slider_label(i, value)
        
        if self.headset_service.set_eq_values(values):
            if self._current_selected_curve_original_name: # Ensure a curve context exists
                # Also update config about this actively applied custom curve
                self.config_manager.set_last_custom_eq_curve_name(self._current_selected_curve_original_name)
                # When editor applies a custom EQ, it becomes the active EQ type for the app.
                self.config_manager.set_setting("active_eq_type", "custom")
                self.eq_applied.emit(self._current_selected_curve_original_name)
        else:
            QMessageBox.warning(self, "EQ Error", "Failed to apply EQ settings to headset on curve load/change.")


    def _get_slider_values(self) -> List[int]:
        return [slider.value() for slider in self.sliders]

    def _discard_changes(self):
        if self._sliders_have_unsaved_changes and self._current_selected_curve_original_name:
            logger.debug(f"Discarding changes for '{self._current_selected_curve_original_name}', reverting to: {self._current_selected_curve_saved_values}")
            self._set_sliders_and_apply(list(self._current_selected_curve_saved_values)) 
            self._sliders_have_unsaved_changes = False
            self._update_ui_for_unsaved_changes_status()

    def _save_curve(self):
        if not self._current_selected_curve_original_name:
            QMessageBox.warning(self, "Save Error", "No curve is currently active to save.")
            return

        name_to_save = self._current_selected_curve_original_name
        values = self._get_slider_values()
        logger.info(f"Saving curve '{name_to_save}' with values: {values}")
        try:
            self.config_manager.save_custom_eq_curve(name_to_save, values)
            self._current_selected_curve_saved_values = list(values) 
            self._sliders_have_unsaved_changes = False
            self._update_ui_for_unsaved_changes_status()
            self.config_manager.set_last_custom_eq_curve_name(name_to_save) 
            # When changes to a curve are saved, it's implied that this custom curve is the active one.
            self.config_manager.set_setting("active_eq_type", "custom") 
            QMessageBox.information(self, "Saved", f"Curve '{name_to_save}' saved.")
        except ValueError as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _save_curve_as(self):
        new_name, ok = QInputDialog.getText(self, "Save Curve As", "Enter new curve name:")
        if not (ok and new_name):
            return 

        new_name = new_name.strip()
        if not new_name:
            QMessageBox.warning(self, "Save As Error", "Curve name cannot be empty.")
            return

        if new_name in self.config_manager.get_all_custom_eq_curves():
            reply = QMessageBox.question(self, "Overwrite",
                                         f"Curve '{new_name}' already exists. Overwrite it?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
        
        values = self._get_slider_values()
        logger.info(f"Saving curve as '{new_name}' with values: {values}")
        try:
            self.config_manager.save_custom_eq_curve(new_name, values)
            self._current_selected_curve_saved_values = list(values) 
            self._sliders_have_unsaved_changes = False
            
            self._load_curve_names_to_combo()
            new_idx = self.curve_combo.findText(new_name)
            if new_idx != -1:
                self.curve_combo.setCurrentIndex(new_idx) 
            else: 
                 if self.curve_combo.count() > 0: self.curve_combo.setCurrentIndex(0)
            
            # After saving as, this new curve becomes the last active custom curve & active EQ type
            self.config_manager.set_last_custom_eq_curve_name(new_name)
            self.config_manager.set_setting("active_eq_type", "custom")
            QMessageBox.information(self, "Saved As", f"Curve '{new_name}' saved.")

        except ValueError as e:
            QMessageBox.critical(self, "Save Error", str(e))


    def _delete_curve(self):
        if not self._current_selected_curve_original_name:
            QMessageBox.warning(self, "Delete Error", "No curve selected to delete.")
            return

        name_to_delete = self._current_selected_curve_original_name
        logger.info(f"Attempting to delete curve: '{name_to_delete}'")
        if name_to_delete in app_config.DEFAULT_EQ_CURVES:
             QMessageBox.warning(self, "Delete Error", f"Cannot delete default curve '{name_to_delete}'.")
             return

        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Are you sure you want to delete curve '{name_to_delete}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.config_manager.delete_custom_eq_curve(name_to_delete)
            logger.info(f"Curve '{name_to_delete}' deleted.")
            
            self._load_curve_names_to_combo() 
            
            # After deletion, select "Flat" or first available and ensure it's applied.
            flat_idx = self.curve_combo.findText(app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME) # Default to Flat
            target_idx_after_delete = flat_idx if flat_idx != -1 else (0 if self.curve_combo.count() > 0 else -1)

            if target_idx_after_delete != -1:
                self.curve_combo.setCurrentIndex(target_idx_after_delete)
                # _on_curve_selected_in_combo will apply the selected (e.g., Flat) EQ and set manager state
            else: # No curves left
                logger.warning("No curves left after deletion. Setting to default flat values.")
                self._current_selected_curve_original_name = None
                self._current_selected_curve_name_in_combo = None
                self._current_selected_curve_saved_values = [0]*10
                self._set_sliders_and_apply([0]*10) 
                self._sliders_have_unsaved_changes = False
                # Explicitly update config manager if no curves are left or Flat is selected.
                # If Flat is default, _on_curve_selected_in_combo will handle it.
                # If all curves deleted, we need to set a "default" active state.
                self.config_manager.set_last_custom_eq_curve_name(app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME)
                self.config_manager.set_setting("active_eq_type", "custom")

            self._update_button_states()