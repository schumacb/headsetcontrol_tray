"""Provides a Qt widget for editing and managing equalizer presets."""

import logging
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from headsetcontrol_tray import app_config
from headsetcontrol_tray import config_manager as cfg_mgr
from headsetcontrol_tray import headset_service as hs_svc

logger = logging.getLogger(f"{app_config.APP_NAME}.{__name__}")

# Constants for QComboBox item data to distinguish EQ types
EQ_TYPE_CUSTOM = "custom"
EQ_TYPE_HARDWARE = "hardware"
HW_PRESET_DISPLAY_PREFIX = "[HW] "


class EqualizerEditorWidget(QWidget):
    """Widget for editing and managing equalizer settings.

    This includes custom curves and hardware presets.
    """

    eq_applied = Signal(
        str,
    )  # Emits name of applied custom curve or "hw_preset:<preset_name>"

    def __init__(
        self,
        config_manager: cfg_mgr.ConfigManager,
        headset_service: hs_svc.HeadsetService,
        parent: QWidget | None = None,
    ) -> None:
        """Initializes the EqualizerEditorWidget.

        Args:
            config_manager: The application's ConfigManager instance.
            headset_service: The application's HeadsetService instance.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.config_manager = config_manager
        self.headset_service = headset_service

        self.sliders: list[QSlider] = []
        self.slider_labels: list[QLabel] = []

        # State for the currently selected *custom* EQ curve (if one is active)
        self._current_custom_curve_original_name: str | None = None
        self._current_custom_curve_saved_values: list[int] = [0] * 10
        self._sliders_have_unsaved_changes: bool = False  # Only for custom EQs

        self._slider_apply_debounce_timer = QTimer(self)
        self._slider_apply_debounce_timer.setSingleShot(True)
        self._slider_apply_debounce_timer.setInterval(250)
        self._slider_apply_debounce_timer.timeout.connect(
            self._apply_sliders_to_headset_and_check_changes,
        )

        self._init_ui()
        self.refresh_view()

    def _init_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)

        # Unified EQ Selection ComboBox
        eq_selection_layout = QHBoxLayout()
        self.eq_combo = QComboBox()
        self.eq_combo.setMinimumWidth(250)
        eq_selection_layout.addWidget(self.eq_combo)

        self.eq_combo.currentIndexChanged.connect(self._on_eq_selected_in_combo)

        # Custom EQ Management Buttons (now includes Discard)
        self.custom_eq_management_buttons_widget = QWidget()
        custom_buttons_layout = QHBoxLayout(self.custom_eq_management_buttons_widget)
        custom_buttons_layout.setContentsMargins(
            0,
            5,
            0,
            5,  # COM812: Trailing comma
        )  # Add some top/bottom margin
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self._save_custom_curve)
        custom_buttons_layout.addWidget(self.save_button)

        self.save_as_button = QPushButton("Save As...")
        self.save_as_button.clicked.connect(self._save_custom_curve_as)
        custom_buttons_layout.addWidget(self.save_as_button)

        self.delete_button = QPushButton("Delete")
        self.delete_button.clicked.connect(self._delete_custom_curve)
        custom_buttons_layout.addWidget(self.delete_button)

        self.discard_button = QPushButton("Discard")
        self.discard_button.clicked.connect(self._discard_slider_changes)
        custom_buttons_layout.addWidget(self.discard_button)
        eq_selection_layout.addWidget(self.custom_eq_management_buttons_widget)
        eq_selection_layout.addStretch()
        main_layout.addLayout(eq_selection_layout)

        # Sliders
        slider_layout = QGridLayout()
        eq_bands_khz = [
            "31",
            "62",
            "125",
            "250",
            "500",
            "1k",
            "2k",
            "4k",
            "8k",
            "16k",
        ]
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
        main_layout.addStretch(1)  # Pushes sliders up if window is tall

    def refresh_view(self) -> None:
        """Refreshes the equalizer editor view, repopulating and selecting the appropriate EQ.

        The UI is updated to reflect the current state.
        """
        logger.debug("EqualizerEditorWidget: Refreshing view")
        self._populate_eq_combo()  # Updates combo items
        # _select_initial_eq_from_config will load the current config state
        # and apply it, which handles ensuring the combo selection is right
        # and the UI (sliders/buttons) reflects that.
        self._select_initial_eq_from_config()

    def _populate_eq_combo(self) -> None:
        self.eq_combo.blockSignals(True)  # noqa: FBT003 # blockSignals only takes positinal Arguments
        current_combo_data = self.eq_combo.currentData()  # Preserve selection if possible
        self.eq_combo.clear()

        custom_curves = self.config_manager.get_all_custom_eq_curves()
        sorted_custom_names = sorted(
            custom_curves.keys(),
            key=lambda x: (x not in app_config.DEFAULT_EQ_CURVES, x.lower()),
        )
        for name in sorted_custom_names:
            self.eq_combo.addItem(name, userData=(EQ_TYPE_CUSTOM, name))

        if custom_curves and app_config.HARDWARE_EQ_PRESET_NAMES:
            self.eq_combo.insertSeparator(self.eq_combo.count())

        for preset_id, name in app_config.HARDWARE_EQ_PRESET_NAMES.items():
            self.eq_combo.addItem(
                HW_PRESET_DISPLAY_PREFIX + name,
                userData=(EQ_TYPE_HARDWARE, preset_id),
            )

        restored_idx = -1
        if current_combo_data:
            for i in range(self.eq_combo.count()):
                if self.eq_combo.itemData(i) == current_combo_data:
                    restored_idx = i
                    break

        if restored_idx != -1:
            self.eq_combo.setCurrentIndex(restored_idx)
        # If not restored, _select_initial_eq_from_config will handle setting the index

        self.eq_combo.blockSignals(False)  # noqa: FBT003 # blockSignals only takes positinal Arguments

    def _select_initial_eq_from_config(self) -> None:
        active_type_from_config = self.config_manager.get_active_eq_type()
        target_data_to_select: tuple[str, Any] | None = None

        if active_type_from_config == EQ_TYPE_HARDWARE:
            preset_id = self.config_manager.get_last_active_eq_preset_id()
            target_data_to_select = (EQ_TYPE_HARDWARE, preset_id)
        else:
            curve_name = self.config_manager.get_last_custom_eq_curve_name()
            if curve_name not in self.config_manager.get_all_custom_eq_curves():
                curve_name = app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME
            target_data_to_select = (EQ_TYPE_CUSTOM, curve_name)

        logger.debug(
            "Selecting initial EQ in combo. Target data: %s",
            target_data_to_select,
        )

        found_idx = -1
        for i in range(self.eq_combo.count()):
            if self.eq_combo.itemData(i) == target_data_to_select:
                found_idx = i
                break

        if found_idx != -1:
            if self.eq_combo.currentIndex() == found_idx:
                # If already selected, still need to process it to update UI
                # state correctly especially if this refresh_view was called externally.
                self._process_eq_selection(
                    self.eq_combo.itemData(found_idx),
                    is_initial_load=True,
                    force_ui_update_only=self._sliders_have_unsaved_changes,
                )

            else:
                self.eq_combo.blockSignals(True)  # noqa: FBT003 # blockSignals only takes positinal Arguments
                self.eq_combo.setCurrentIndex(found_idx)
                self.eq_combo.blockSignals(False)  # noqa: FBT003 # blockSignals only takes positinal Arguments
                self._process_eq_selection(
                    self.eq_combo.itemData(found_idx),
                    is_initial_load=True,
                )
        elif self.eq_combo.count() > 0:
            logger.warning(
                "Initial EQ target %s not found in combo. Selecting first available.",
                target_data_to_select,
            )
            self.eq_combo.blockSignals(True)  # noqa: FBT003 # blockSignals only takes positinal Arguments
            self.eq_combo.setCurrentIndex(0)
            self.eq_combo.blockSignals(False)  # noqa: FBT003 # blockSignals only takes positinal Arguments
            self._process_eq_selection(self.eq_combo.itemData(0), is_initial_load=True)
        else:
            logger.error("EQ combo is empty. Cannot select initial EQ.")
            self._update_ui_for_active_eq(None, None)

    def _on_eq_selected_in_combo(self, index: int) -> None:
        if index == -1:
            return
        selected_data = self.eq_combo.itemData(index)
        if not selected_data:
            logger.warning("EQ combo selected item has no data.")
            return

        logger.debug(
            "User selected EQ in combo: %s, Data: %s",
            self.eq_combo.itemText(index),
            selected_data,
        )
        self._process_eq_selection(selected_data, is_initial_load=False)

    def _handle_custom_eq_selection(
        self,
        curve_name: str,
        *,
        is_initial_load: bool,
        force_ui_update_only: bool,
    ) -> None:
        # Only update _current_custom_curve_original_name if it's different
        # or force_ui_update_only is false. This helps preserve the
        # "active editing" context if refresh_view is called while sliders are
        # dirty.
        if not (
            force_ui_update_only
            and self._current_custom_curve_original_name == curve_name
            and self._sliders_have_unsaved_changes
        ):
            self._current_custom_curve_original_name = curve_name

        values = self.config_manager.get_custom_eq_curve(curve_name)
        if not values:
            logger.warning(
                ("Custom curve '%s' not found in config manager. Defaulting to flat."),
                curve_name,
            )
            values = app_config.DEFAULT_EQ_CURVES.get("Flat", [0] * 10)

        # Update saved values only if not preserving unsaved changes
        if not (
            force_ui_update_only
            and self._current_custom_curve_original_name == curve_name
            and self._sliders_have_unsaved_changes
        ):
            self._current_custom_curve_saved_values = list(values)

        # If force_ui_update_only is true AND there are unsaved changes for
        # this curve, do NOT reset sliders from saved values. Let them be.
        if not (
            force_ui_update_only
            and self._current_custom_curve_original_name == curve_name
            and self._sliders_have_unsaved_changes
        ):
            self._set_slider_visuals(values)
            if not is_initial_load:  # Only reset unsaved changes if it's a new selection by user
                self._sliders_have_unsaved_changes = False

        # Apply to headset only on user action or if not preserving UI for
        # unsaved changes
        if not is_initial_load and not force_ui_update_only:
            float_values = [float(v) for v in values]
            if self.headset_service.set_eq_values(float_values):
                self.config_manager.set_setting("active_eq_type", EQ_TYPE_CUSTOM)
                self.config_manager.set_last_custom_eq_curve_name(curve_name)
                self.eq_applied.emit(curve_name)
            else:
                QMessageBox.warning(
                    self,
                    "EQ Error",
                    "Failed to apply custom EQ to headset.",
                )

        # If it's just a UI refresh due to external change, but user was editing
        # this curve, ensure _sliders_have_unsaved_changes reflects the
        # current slider vs saved state.
        if force_ui_update_only and self._current_custom_curve_original_name == curve_name:
            current_slider_vals = self._get_slider_values()
            self._sliders_have_unsaved_changes = current_slider_vals != self._current_custom_curve_saved_values

    def _handle_hardware_eq_selection(
        self,
        preset_id: int,
        eq_data: tuple[str, Any],  # eq_data is passed to get display name
        *,
        is_initial_load: bool,
        force_ui_update_only: bool,
    ) -> None:
        preset_name_display = ""
        # Get display name for signal
        for i in range(self.eq_combo.count()):
            if self.eq_combo.itemData(i) == eq_data:
                preset_name_display = self.eq_combo.itemText(i).replace(
                    HW_PRESET_DISPLAY_PREFIX,
                    "",
                )
                break

        self._current_custom_curve_original_name = None
        self._sliders_have_unsaved_changes = False  # No unsaved changes for HW presets
        self._set_slider_visuals([0] * 10)  # Sliders are disabled for HW, show flat

        if not is_initial_load and not force_ui_update_only:
            if self.headset_service.set_eq_preset_id(preset_id):
                self.config_manager.set_setting("active_eq_type", EQ_TYPE_HARDWARE)
                self.config_manager.set_last_active_eq_preset_id(preset_id)
                self.eq_applied.emit(f"hw_preset:{preset_name_display}")
            else:
                QMessageBox.warning(
                    self,
                    "EQ Error",
                    f"Failed to apply HW preset '{preset_name_display}'.",
                )

    def _process_eq_selection(
        self,
        eq_data: tuple[str, Any],
        *,
        is_initial_load: bool = False,
        force_ui_update_only: bool = False,
    ) -> None:
        eq_type, eq_identifier = eq_data

        if eq_type == EQ_TYPE_CUSTOM:
            self._handle_custom_eq_selection(
                curve_name=eq_identifier,
                is_initial_load=is_initial_load,  # Changed to keyword argument
                force_ui_update_only=force_ui_update_only,  # Changed to keyword argument
            )
        elif eq_type == EQ_TYPE_HARDWARE:
            self._handle_hardware_eq_selection(
                preset_id=eq_identifier,
                eq_data=eq_data,
                is_initial_load=is_initial_load,  # Changed to keyword argument
                force_ui_update_only=force_ui_update_only,  # Changed to keyword argument
            )
        # Add handling for other types or None if necessary
        else:
            logger.warning("Unknown EQ type selected: %s", eq_type)
            # Potentially reset UI to a default "no EQ active" state
            self._current_custom_curve_original_name = None
            self._sliders_have_unsaved_changes = False
            self._set_slider_visuals([0] * 10)

        self._update_ui_for_active_eq(eq_type, eq_identifier)

    def _update_custom_eq_buttons_state(
        self,
        *,
        is_custom_mode_active: bool,
        active_identifier: Any | None,
    ) -> None:
        self.custom_eq_management_buttons_widget.setVisible(
            True,
        )  # Always visible for now

        can_save = (
            is_custom_mode_active
            and self._sliders_have_unsaved_changes
            and bool(self._current_custom_curve_original_name)
        )
        self.save_button.setEnabled(can_save)

        self.save_as_button.setEnabled(is_custom_mode_active)

        can_delete = is_custom_mode_active and bool(
            active_identifier  # This is the curve name for custom EQ
            and active_identifier not in app_config.DEFAULT_EQ_CURVES,
        )
        self.delete_button.setEnabled(can_delete)

        self.discard_button.setEnabled(
            is_custom_mode_active and self._sliders_have_unsaved_changes,
        )

    def _update_combo_text_for_unsaved_changes(
        self,
        *,
        is_custom_mode_active: bool,
    ) -> None:
        if is_custom_mode_active and self._current_custom_curve_original_name:
            self.eq_combo.blockSignals(True)  # noqa: FBT003 # blockSignals only takes positinal Arguments
            active_curve_name = self._current_custom_curve_original_name
            for i in range(self.eq_combo.count()):
                item_data = self.eq_combo.itemData(i)
                if item_data and item_data[0] == EQ_TYPE_CUSTOM and item_data[1] == active_curve_name:
                    text_to_display = active_curve_name
                    if self._sliders_have_unsaved_changes:
                        text_to_display += "*"
                    if self.eq_combo.itemText(i) != text_to_display:
                        self.eq_combo.setItemText(i, text_to_display)
                    # No need to force selection here, this is about text update
                    break

            # If the current combo selection IS NOT the active custom curve,
            # but it's a custom curve and has an asterisk, remove it.
            # Also handles cases where a custom curve was active, user switched to HW,
            # then this is called.
            current_idx = self.eq_combo.currentIndex()
            current_selection_data = self.eq_combo.itemData(current_idx)
            if current_selection_data and current_selection_data[0] == EQ_TYPE_CUSTOM:
                selected_curve_name = current_selection_data[1]
                if selected_curve_name != active_curve_name and self.eq_combo.itemText(
                    current_idx,
                ).endswith("*"):
                    original_text = self.eq_combo.itemText(current_idx).rstrip("*")
                    self.eq_combo.setItemText(current_idx, original_text)

            self.eq_combo.blockSignals(False)  # noqa: FBT003 # blockSignals only takes positinal Arguments
        elif not is_custom_mode_active:
            # If not in custom mode, remove all unsaved indicators
            self._remove_all_unsaved_indicators_from_combo()

    def _update_ui_for_active_eq(
        self,
        active_eq_type: str | None,
        active_identifier: Any | None,  # curve_name or preset_id
    ) -> None:
        is_custom_mode_active = active_eq_type == EQ_TYPE_CUSTOM

        for slider in self.sliders:
            slider.setEnabled(is_custom_mode_active)

        self._update_custom_eq_buttons_state(
            is_custom_mode_active=is_custom_mode_active,
            active_identifier=active_identifier,
        )
        self._update_combo_text_for_unsaved_changes(is_custom_mode_active=is_custom_mode_active)

    def _remove_all_unsaved_indicators_from_combo(self) -> None:
        self.eq_combo.blockSignals(True)  # noqa: FBT003 # blockSignals only takes positinal Arguments
        current_idx = self.eq_combo.currentIndex()  # Preserve if it's a HW preset
        for i in range(self.eq_combo.count()):
            item_data = self.eq_combo.itemData(i)
            if item_data and item_data[0] == EQ_TYPE_CUSTOM:
                original_name = item_data[1]
                if self.eq_combo.itemText(i).endswith("*"):
                    self.eq_combo.setItemText(i, original_name)
        if current_idx != -1:
            self.eq_combo.setCurrentIndex(current_idx)
        self.eq_combo.blockSignals(False)  # noqa: FBT003 # blockSignals only takes positinal Arguments

    def _update_slider_label(self, index: int, value: int) -> None:
        self.slider_labels[index].setText(f"{value} dB")

    def _on_slider_value_changed(self, value: int) -> None:
        active_data = self.eq_combo.currentData()
        if not active_data or active_data[0] != EQ_TYPE_CUSTOM:
            return

        sender_obj = self.sender()
        if isinstance(sender_obj, QSlider) and sender_obj in self.sliders:
            self._update_slider_label(self.sliders.index(sender_obj), value)
        # Mark unsaved changes immediately when slider moves
        current_slider_vals = self._get_slider_values()
        if self._current_custom_curve_original_name:
            self._sliders_have_unsaved_changes = current_slider_vals != self._current_custom_curve_saved_values
        self._update_ui_for_active_eq(
            EQ_TYPE_CUSTOM,
            self._current_custom_curve_original_name,
        )  # Update '*' and button states

        self._slider_apply_debounce_timer.start()  # Then apply to headset after debounce

    def _apply_sliders_to_headset_and_check_changes(
        self,
    ) -> None:  # Renamed for clarity, only applies, doesn't re-check changes flag here
        active_data = self.eq_combo.currentData()
        if not active_data or active_data[0] != EQ_TYPE_CUSTOM:
            return

        current_values = self._get_slider_values()
        logger.debug("Applying slider values to headset: %s", current_values)
        float_current_values = [float(v) for v in current_values]
        if self.headset_service.set_eq_values(float_current_values):
            logger.info(
                "EQ_EDITOR: Sliders applied, set_eq_values SUCCESS for '%s'",
                self._current_custom_curve_original_name,
            )
            if self._current_custom_curve_original_name:
                # On successful application, update ConfigManager for the active curve
                self.config_manager.set_setting("active_eq_type", EQ_TYPE_CUSTOM)
                self.config_manager.set_last_custom_eq_curve_name(
                    self._current_custom_curve_original_name,
                )
                self.eq_applied.emit(
                    self._current_custom_curve_original_name,
                )  # Notify tray
        else:
            logger.error(
                "EQ_EDITOR: Sliders applied, set_eq_values FAILED for '%s'",
                self._current_custom_curve_original_name,
            )
            QMessageBox.warning(
                self,
                "EQ Error",
                "Failed to apply EQ settings to headset.",
            )

        # The _sliders_have_unsaved_changes flag and UI update (like '*') were
        # already handled by _on_slider_value_changed.
        # This function's main job is now just the headset application.

    def _set_slider_visuals(self, values: list[int]) -> None:
        for i, value in enumerate(values):
            self.sliders[i].blockSignals(True)  # noqa: FBT003 # blockSignals only takes positinal Arguments
            self.sliders[i].setValue(value)
            self.sliders[i].blockSignals(False)  # noqa: FBT003 # blockSignals only takes positinal Arguments
            self._update_slider_label(i, value)

    def _get_slider_values(self) -> list[int]:
        return [s.value() for s in self.sliders]

    def _discard_slider_changes(self) -> None:
        active_data = self.eq_combo.currentData()
        if not (
            active_data
            and active_data[0] == EQ_TYPE_CUSTOM
            and self._sliders_have_unsaved_changes
            and self._current_custom_curve_original_name
        ):
            return

        logger.debug(
            "Discarding slider changes for '%s'",
            self._current_custom_curve_original_name,
        )
        self._set_slider_visuals(
            list(self._current_custom_curve_saved_values),
        )  # Revert visuals

        # Re-apply the saved values to the headset
        float_saved_values = [float(v) for v in self._current_custom_curve_saved_values]
        if self.headset_service.set_eq_values(float_saved_values):
            logger.info(
                "EQ_EDITOR: Discarded changes, set_eq_values SUCCESS for '%s'",
                self._current_custom_curve_original_name,
            )
            # Ensure config reflects this (it should already, but to be safe)
            self.config_manager.set_setting("active_eq_type", EQ_TYPE_CUSTOM)
            self.config_manager.set_last_custom_eq_curve_name(
                self._current_custom_curve_original_name,
            )
            self.eq_applied.emit(self._current_custom_curve_original_name)
        else:
            logger.error(
                "EQ_EDITOR: Discarded changes, set_eq_values FAILED for '%s'",
                self._current_custom_curve_original_name,
            )

        self._sliders_have_unsaved_changes = False
        self._update_ui_for_active_eq(
            EQ_TYPE_CUSTOM,
            self._current_custom_curve_original_name,
        )

    def _save_custom_curve(self) -> None:
        active_data = self.eq_combo.currentData()
        if not (active_data and active_data[0] == EQ_TYPE_CUSTOM and self._current_custom_curve_original_name):
            QMessageBox.warning(
                self,
                "Save Error",
                "No custom curve active to save.",
            )  # Wrapped
            return

        name_to_save = self._current_custom_curve_original_name
        values = self._get_slider_values()
        try:
            self.config_manager.save_custom_eq_curve(name_to_save, values)
            self._current_custom_curve_saved_values = list(values)
            self._sliders_have_unsaved_changes = False

            # Ensure config manager is updated regarding the active state
            self.config_manager.set_setting("active_eq_type", EQ_TYPE_CUSTOM)
            self.config_manager.set_last_custom_eq_curve_name(name_to_save)
            self.eq_applied.emit(name_to_save)

            QMessageBox.information(self, "Saved", f"Curve '{name_to_save}' saved.")
        except ValueError as e:
            QMessageBox.critical(self, "Save Error", str(e))
        # Update UI: remove '*', disable save button etc.
        self._update_ui_for_active_eq(EQ_TYPE_CUSTOM, name_to_save)

    def _save_custom_curve_as(self) -> None:
        new_name, ok = QInputDialog.getText(
            self,
            "Save Curve As",
            "Enter new curve name:",
        )
        if not (ok and new_name.strip()):
            return
        new_name = new_name.strip()
        if (
            new_name in self.config_manager.get_all_custom_eq_curves()
            and QMessageBox.question(
                self,
                "Overwrite",
                f"Curve '{new_name}' exists. Overwrite?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,  # COM812: Trailing comma
            )
            == QMessageBox.StandardButton.No
        ):
            return

        values = self._get_slider_values()
        try:
            self.config_manager.save_custom_eq_curve(new_name, values)
            self._current_custom_curve_original_name = new_name  # This is now the active curve
            self._current_custom_curve_saved_values = list(values)
            self._sliders_have_unsaved_changes = False

            self._populate_eq_combo()  # Repopulate to include the new curve

            new_curve_data = (EQ_TYPE_CUSTOM, new_name)
            found_idx = -1
            for i in range(self.eq_combo.count()):
                if self.eq_combo.itemData(i) == new_curve_data:
                    found_idx = i
                    break

            self.eq_combo.blockSignals(True)  # noqa: FBT003 # blockSignals only takes positinal Arguments
            if found_idx != -1:
                self.eq_combo.setCurrentIndex(found_idx)
            else:
                logger.error(
                    "Could not find newly saved curve '%s' in combo.",
                    new_name,
                )
                self._select_initial_eq_from_config()
            self.eq_combo.blockSignals(False)  # noqa: FBT003 # blockSignals only takes positinal Arguments

            # After setCurrentIndex, _on_eq_selected_in_combo will fire, which
            # calls _process_eq_selection. This will handle setting config and
            # emitting eq_applied. So, explicitly calling _process_eq_selection
            # here might be redundant or cause double-processing. Let's rely on
            # the signal from setCurrentIndex. If it was blocked during the index
            # set, we'd need to call _process_eq_selection manually. Since it's
            # unblocked before setCurrentIndex, the signal should fire.

            # Manually process if the index didn't change but we need to register
            # it as the active one
            if self.eq_combo.currentIndex() == found_idx:
                self._process_eq_selection(
                    new_curve_data,
                    is_initial_load=False,
                    force_ui_update_only=False,
                )  # Ensure all args are keywords

            QMessageBox.information(self, "Saved As", f"Curve '{new_name}' saved.")

        except ValueError as e:
            QMessageBox.critical(self, "Save Error", str(e))

    def _delete_custom_curve(self) -> None:
        active_data = self.eq_combo.currentData()
        if not (active_data and active_data[0] == EQ_TYPE_CUSTOM and self._current_custom_curve_original_name):
            QMessageBox.warning(
                self,
                "Delete Error",
                "No custom curve selected to delete.",
            )
            return

        name_to_delete = self._current_custom_curve_original_name
        if name_to_delete in app_config.DEFAULT_EQ_CURVES:
            QMessageBox.warning(
                self,
                "Delete Error",
                f"Cannot delete default curve '{name_to_delete}'.",
            )
            return

        if (
            QMessageBox.question(
                self,
                "Confirm Delete",
                f"Delete curve '{name_to_delete}'?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            == QMessageBox.StandardButton.Yes
        ):
            self.config_manager.delete_custom_eq_curve(name_to_delete)
            logger.info("Curve '%s' deleted.", name_to_delete)

            self._current_custom_curve_original_name = None
            self._sliders_have_unsaved_changes = False

            self._populate_eq_combo()
            flat_data = (EQ_TYPE_CUSTOM, app_config.DEFAULT_CUSTOM_EQ_CURVE_NAME)
            idx_to_select = -1
            for i in range(self.eq_combo.count()):
                if self.eq_combo.itemData(i) == flat_data:
                    idx_to_select = i
                    break

            if idx_to_select == -1 and self.eq_combo.count() > 0:
                idx_to_select = 0

            if idx_to_select != -1:
                self.eq_combo.blockSignals(True)  # noqa: FBT003 # blockSignals only takes positinal Arguments
                self.eq_combo.setCurrentIndex(idx_to_select)
                self.eq_combo.blockSignals(False)  # noqa: FBT003 # blockSignals only takes positinal Arguments
                self._process_eq_selection(
                    self.eq_combo.itemData(idx_to_select),
                    is_initial_load=False,
                )
            else:
                logger.error(
                    "No EQs left after deletion, this state should be handled.",
                )
                self._update_ui_for_active_eq(None, None)
