# steelseries_tray/ui/equalizer_editor_dialog.py
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QSlider, QLabel, QPushButton,
    QComboBox, QLineEdit, QMessageBox, QSpacerItem, QSizePolicy, QGridLayout
)
from PySide6.QtCore import Qt, Signal
from typing import List, Optional

from .. import config_manager as cfg_mgr
from .. import headset_service as hs_svc
from .. import app_config

class EqualizerEditorDialog(QDialog):
    """Dialog for editing and managing custom equalizer curves."""
    eq_applied = Signal(str) # Emits name of applied custom curve
    hardware_preset_applied = Signal(int) # Emits ID of applied hardware preset

    def __init__(self, config_manager: cfg_mgr.ConfigManager, headset_service: hs_svc.HeadsetService, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.headset_service = headset_service

        self.setWindowTitle("Equalizer Editor")
        self.setMinimumWidth(500)

        self.sliders: List[QSlider] = []
        self.slider_labels: List[QLabel] = []
        self.current_curve_name: Optional[str] = None

        self._init_ui()
        self._load_curve_names()
        self._select_initial_curve()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)

        # Curve selection and management
        manage_layout = QHBoxLayout()
        self.curve_combo = QComboBox()
        self.curve_combo.setMinimumWidth(200)
        self.curve_combo.currentTextChanged.connect(self._on_curve_selected)
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

        self.curve_name_edit = QLineEdit()
        self.curve_name_edit.setPlaceholderText("Enter new curve name for 'Save As'")
        main_layout.addWidget(self.curve_name_edit)

        # Sliders
        slider_layout = QGridLayout()
        # Approximate frequencies for labels, could be more accurate
        eq_bands_khz = ["31", "62", "125", "250", "500", "1k", "2k", "4k", "8k", "16k"] # Hz/kHz labels
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
            slider.valueChanged.connect(lambda val, index=i: self._update_slider_label(index, val))
            self.sliders.append(slider)
            slider_vbox.addWidget(slider, alignment=Qt.AlignmentFlag.AlignCenter)

            label = QLabel("0 dB")
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.slider_labels.append(label)
            slider_vbox.addWidget(label)
            
            slider_layout.addLayout(slider_vbox, 0, i)

        main_layout.addLayout(slider_layout)

        # Apply and Close buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        self.apply_button = QPushButton("Apply EQ")
        self.apply_button.clicked.connect(self._apply_eq)
        button_layout.addWidget(self.apply_button)

        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)
        main_layout.addLayout(button_layout)

    def _update_slider_label(self, index: int, value: int):
        self.slider_labels[index].setText(f"{value} dB")

    def _load_curve_names(self):
        self.curve_combo.blockSignals(True)
        self.curve_combo.clear()
        curves = self.config_manager.get_all_custom_eq_curves()
        sorted_names = sorted(curves.keys(), key=lambda x: (x not in app_config.DEFAULT_EQ_CURVES, x))
        for name in sorted_names:
            self.curve_combo.addItem(name)
        self.curve_combo.blockSignals(False)

    def _select_initial_curve(self):
        active_type = self.config_manager.get_active_eq_type()
        last_custom_name = self.config_manager.get_last_custom_eq_curve_name()
        
        if active_type == "custom" and last_custom_name:
            idx = self.curve_combo.findText(last_custom_name)
            if idx != -1:
                self.curve_combo.setCurrentIndex(idx)
                self._load_curve_values(last_custom_name)
                return

        # Fallback to first item or default Flat if available
        if self.curve_combo.count() > 0:
            flat_idx = self.curve_combo.findText("Flat")
            self.curve_combo.setCurrentIndex(flat_idx if flat_idx != -1 else 0)
            self._load_curve_values(self.curve_combo.currentText())
        else: # Should not happen if defaults are loaded
            self._set_sliders([0]*10)


    def _on_curve_selected(self, name: str):
        if name:
            self._load_curve_values(name)
            self.curve_name_edit.setText(name) # For easy 'Save'

    def _load_curve_values(self, name: str):
        values = self.config_manager.get_custom_eq_curve(name)
        if values:
            self._set_sliders(values)
            self.current_curve_name = name
            self.curve_name_edit.setText(name)
        else: # Should not happen if combo is populated correctly
             self._set_sliders([0]*10) # Default to flat if somehow name is invalid
             self.current_curve_name = None
             self.curve_name_edit.clear()


    def _set_sliders(self, values: List[int]):
        for i, value in enumerate(values):
            self.sliders[i].setValue(value)
            self._update_slider_label(i, value)

    def _get_slider_values(self) -> List[int]:
        return [slider.value() for slider in self.sliders]

    def _apply_eq(self):
        values = self._get_slider_values()
        if self.headset_service.set_eq_values(values):
            QMessageBox.information(self, "Success", "Equalizer settings applied to headset.")
            current_selection_name = self.curve_combo.currentText()
            if current_selection_name: # if a known curve is selected and applied
                 self.config_manager.set_last_custom_eq_curve_name(current_selection_name)
                 self.eq_applied.emit(current_selection_name)
            # If sliders were manually changed and 'Apply' hit without saving,
            # it applies the current slider values. The active curve remains the one selected in combo,
            # or becomes "custom unsaved" implicitly.
        else:
            QMessageBox.warning(self, "Error", "Failed to apply equalizer settings.")

    def _save_curve(self):
        name_to_save = self.curve_combo.currentText()
        if not name_to_save: # Should not happen if combo has items
            QMessageBox.warning(self, "Save Error", "No curve selected to save.")
            return

        # Check if trying to save over a default curve that's not "Flat" (allow Flat to be customized)
        # Or provide a "Reset Defaults" option separately. For now, allow overwrite.
        # if name_to_save in app_config.DEFAULT_EQ_CURVES and name_to_save != "Flat":
        #     reply = QMessageBox.question(self, "Overwrite Default",
        #                                  f"'{name_to_save}' is a default curve. Overwrite it?",
        #                                  QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        #     if reply == QMessageBox.StandardButton.No:
        #         return

        values = self._get_slider_values()
        try:
            self.config_manager.save_custom_eq_curve(name_to_save, values)
            QMessageBox.information(self, "Saved", f"Curve '{name_to_save}' saved.")
            self.current_curve_name = name_to_save
            # No need to reload_curve_names if only values changed for existing name
        except ValueError as e:
            QMessageBox.critical(self, "Save Error", str(e))


    def _save_curve_as(self):
        new_name = self.curve_name_edit.text().strip()
        if not new_name:
            QMessageBox.warning(self, "Save As Error", "Please enter a name for the new curve.")
            return

        if new_name in self.config_manager.get_all_custom_eq_curves():
            reply = QMessageBox.question(self, "Overwrite",
                                         f"Curve '{new_name}' already exists. Overwrite it?",
                                         QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                return
        
        values = self._get_slider_values()
        try:
            self.config_manager.save_custom_eq_curve(new_name, values)
            QMessageBox.information(self, "Saved As", f"Curve '{new_name}' saved.")
            self._load_curve_names() # Reload combo box
            self.curve_combo.setCurrentText(new_name) # Select the new curve
            self.current_curve_name = new_name
        except ValueError as e:
            QMessageBox.critical(self, "Save Error", str(e))


    def _delete_curve(self):
        name_to_delete = self.curve_combo.currentText()
        if not name_to_delete:
            QMessageBox.warning(self, "Delete Error", "No curve selected to delete.")
            return

        if name_to_delete in app_config.DEFAULT_EQ_CURVES:
             QMessageBox.warning(self, "Delete Error", f"Cannot delete default curve '{name_to_delete}'. You can modify it.")
             return

        reply = QMessageBox.question(self, "Confirm Delete",
                                     f"Are you sure you want to delete curve '{name_to_delete}'?",
                                     QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            self.config_manager.delete_custom_eq_curve(name_to_delete)
            self._load_curve_names()
            # Select first available curve or Flat after deletion
            if self.curve_combo.count() > 0:
                flat_idx = self.curve_combo.findText(app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME)
                idx_to_select = flat_idx if flat_idx != -1 else 0
                self.curve_combo.setCurrentIndex(idx_to_select)
                self._load_curve_values(self.curve_combo.currentText())
            else: # All curves deleted, which implies defaults were also deleted (not ideal)
                self._set_sliders([0]*10)
                self.curve_name_edit.clear()


    def get_selected_values(self) -> Optional[List[int]]:
        """Returns the current slider values if the dialog is accepted."""
        if self.result() == QDialog.DialogCode.Accepted: # Or via an "Apply" button
            return self._get_slider_values()
        return None