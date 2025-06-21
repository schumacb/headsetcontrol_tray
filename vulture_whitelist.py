# vulture_whitelist.py
# Placeholder for items that are intentionally unused or Vulture false positives.

# tests/test_app.py
_mock_system_tray_icon  # Used as a pytest fixture via @pytest.mark.usefixtures
udev_setup_details  # Attribute set on a mock object for configuration/state

# tests/test_config_manager.py
# Whitelist mocked_app_config only if it's confirmed to be a false positive after review.
# If it's truly unused, it should be removed, not whitelisted.
# For now, assume it might be used for mock configuration or side effects.
mocked_app_config  # Return value of patcher.start(), patch itself is used
mock_json_load_with_side_effect  # Patched mock object, used for its side effect configuration in test
_settings_file_path  # Attribute on a mock object, set for test verification via another method call
_custom_eq_curves_file_path  # Attribute on a mock object, set for test verification via another method call
