import pytest
import verboselogs
import logging

@pytest.fixture(autouse=True, scope="session")
def install_verboselogs_for_tests():
    """
    Ensures that verboselogs is installed (monkeypatches logging)
    once for the entire test session.
    """
    try:
        verboselogs.install()
        # print("verboselogs installed for test session.") # Optional: for debugging
    except Exception as e:
        # print(f"Error installing verboselogs: {e}") # Optional: for debugging
        # Depending on strictness, you might want to fail tests if this doesn't work.
        pass

    # Optional: If you want to ensure a certain log level for tests globally
    # logging.basicConfig(level=logging.DEBUG) # Or any other desired level
    # Note: Be cautious with basicConfig if pytest or other fixtures also configure logging.
    # Usually, pytest's own logging caplog fixture or config options are preferred for test log control.
