import unittest
from unittest.mock import patch, Mock
import os
import sys

# Ensure the application modules can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from PySide6.QtWidgets import QApplication

# Modules to be tested or mocked
try:
    from headsetcontrol_tray.app import SteelSeriesTrayApp
    # Import HeadsetService from its original location to mock it where it's defined
    from headsetcontrol_tray import headset_service as hs_svc_module
except ImportError as e:
    print(f"ImportError in test_app.py: {e}")
    # This indicates a potential issue with the sys.path manipulation or project structure
    # For now, we'll let it fail loudly if imports don't work, as it's critical for tests.
    raise


class TestSteelSeriesTrayAppUdevDialog(unittest.TestCase):

    def setUp(self):
        """Ensure a QApplication instance exists for each test."""
        # QApplication.instance() returns the existing instance or None
        if not QApplication.instance():
            self.app = QApplication(sys.argv) # Create if no instance exists
        else:
            self.app = QApplication.instance()

    @patch('headsetcontrol_tray.app.sti.SystemTrayIcon') # Mock SystemTrayIcon to prevent it from showing
    @patch('headsetcontrol_tray.app.QMessageBox') # Mock QMessageBox to check calls
    @patch('headsetcontrol_tray.app.hs_svc.HeadsetService') # Mock HeadsetService class
    def test_udev_dialog_shown_when_details_present(self,
                                                 MockHeadsetService,
                                                 mock_qmessagebox,
                                                 MockSystemTrayIcon):
        # 1. Configure the mock HeadsetService instance
        mock_service_instance = MockHeadsetService.return_value # This is what `HeadsetService()` will return

        # Set up the udev_setup_details attribute on this instance
        sample_details = {
            "temp_file_path": "/tmp/test_rules.txt",
            "final_file_path": "/etc/udev/rules.d/99-test-rules.rules",
            "rule_filename": "99-test-rules.rules"
        }
        mock_service_instance.udev_setup_details = sample_details

        # Mock other methods/attributes of HeadsetService instance that might be called during SteelSeriesTrayApp.__init__
        mock_service_instance.is_device_connected = Mock(return_value=True) # Assume device is connected for this test
        mock_service_instance.close = Mock()

        # 2. Instantiate SteelSeriesTrayApp. This will call HeadsetService() internally,
        #    which will return our mock_service_instance.
        #    The __init__ of SteelSeriesTrayApp should then check udev_setup_details.
        try:
            tray_app_instance = SteelSeriesTrayApp()
        except Exception as e:
            self.fail(f"SteelSeriesTrayApp instantiation failed: {e}")

        # 3. Assert that QMessageBox.information was called
        mock_qmessagebox.information.assert_called_once()

        # 4. Optionally, assert some call arguments
        #    The call is QMessageBox.information(None, title, message_string)
        args, kwargs = mock_qmessagebox.information.call_args

        # Check title
        self.assertEqual(args[1], "Headset Permissions Setup Required")

        # Check parts of the message string
        self.assertIn(sample_details["temp_file_path"], args[2])
        self.assertIn(sample_details["final_file_path"], args[2])
        self.assertIn("sudo cp", args[2])
        self.assertIn("sudo udevadm control --reload-rules", args[2])

    @patch('headsetcontrol_tray.app.sti.SystemTrayIcon')
    @patch('headsetcontrol_tray.app.QMessageBox')
    @patch('headsetcontrol_tray.app.hs_svc.HeadsetService')
    def test_udev_dialog_not_shown_when_details_absent(self,
                                                      MockHeadsetService,
                                                      mock_qmessagebox,
                                                      MockSystemTrayIcon):
        # Configure the mock HeadsetService instance
        mock_service_instance = MockHeadsetService.return_value
        mock_service_instance.udev_setup_details = None # Crucial: no details
        mock_service_instance.is_device_connected = Mock(return_value=True)
        mock_service_instance.close = Mock()

        try:
            tray_app_instance = SteelSeriesTrayApp()
        except Exception as e:
            self.fail(f"SteelSeriesTrayApp instantiation failed: {e}")

        # Assert that QMessageBox.information was NOT called
        mock_qmessagebox.information.assert_not_called()


if __name__ == '__main__':
    unittest.main()
