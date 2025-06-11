"""Whitelist for Vulture to ignore specific false positives."""

# Vulture patterns to ignore. Vulture needs to be configured to find this list
# or these patterns need to be extracted and fed to its CLI.
# The format "_._attribute_name" is a Vulture pattern that typically means
# "ignore 'attribute_name' on any instance".

VULTURE_WHITELIST = [
    "_._settings  # unused attribute (tests/test_config_manager.py:234)",
    "_._settings  # unused attribute (tests/test_config_manager.py:245)",
    "_._settings  # unused attribute (tests/test_config_manager.py:310)",
    "_._settings  # unused attribute (tests/test_config_manager.py:326)",
    "_._settings  # unused attribute (tests/test_config_manager.py:402)",
    "_._settings  # unused attribute (tests/test_config_manager.py:405)",
    "_._settings  # unused attribute (tests/test_config_manager.py:412)",
    "_._settings  # unused attribute (tests/test_config_manager.py:419)",
    "_._settings  # unused attribute (tests/test_config_manager.py:426)",
    "_._settings  # unused attribute (tests/test_config_manager.py:430)",
    "_._settings  # unused attribute (tests/test_config_manager.py:434)",
    "_._settings  # unused attribute (tests/test_config_manager.py:440)",
    "_._settings  # unused attribute (tests/test_config_manager.py:464)",
    "_._settings  # unused attribute (tests/test_config_manager.py:466)",
    "_._settings  # unused attribute (tests/test_config_manager.py:473)",
    "_._settings  # unused attribute (tests/test_config_manager.py:475)",
    "_._settings  # unused attribute (tests/test_config_manager.py:482)",
    "_._settings  # unused attribute (tests/test_config_manager.py:484)",
    "_._settings  # unused attribute (tests/test_config_manager.py:491)",
    "_._settings  # unused attribute (tests/test_config_manager.py:493)",
    "_._settings  # unused attribute (tests/test_config_manager.py:500)",
    "_._settings  # unused attribute (tests/test_config_manager.py:502)",
    "_._settings  # unused attribute (tests/test_config_manager.py:509)",
    "_._settings  # unused attribute (tests/test_config_manager.py:511)",
    "_._settings  # unused attribute (tests/test_config_manager.py:520)",
    "_._settings  # unused attribute (tests/test_config_manager.py:522)",
    "_._settings  # unused attribute (tests/test_config_manager.py:529)",
    "_._settings  # unused attribute (tests/test_config_manager.py:531)",
]

# To make Vulture use this, you might need to adjust Vulture's invocation, e.g.:
# vulture --ignore-names-from-file tests/whitelist.py (if Vulture supports this directly for lists)
# or extract patterns from this file using a script and pass to Vulture.
# Or, more commonly, Vulture might look for a specific filename like '.vulture_whitelist.py'
# and expect patterns one per line (not necessarily as Python strings).
# This format makes the file valid Python for other linters (Ruff, Mypy).
