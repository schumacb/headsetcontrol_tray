# Vulture whitelist

# tests/test_app.py
_mock_system_tray_icon  # Used as a pytest fixture via @pytest.mark.usefixtures, essential for its side effect (patching).
udev_setup_details  # Attribute set on a mock object for test case configuration/state, not dead code.

# tests/test_config_manager.py
mocked_app_config # Return value of patcher.start(), the patch itself is used for its side effects on app_config.
