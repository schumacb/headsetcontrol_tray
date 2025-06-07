This plan addresses key findings from code reviews and automated tool reports to improve code quality, fix test failures, and resolve type errors. Items are prioritized.
1.  **Fix QApplication singleton errors in `test_app.py`.** (Priority: 1)
    *   **Details:** Multiple tests in `test_app.py` (e.g., TestSteelSeriesTrayAppUdevDialog methods) try to create new QApplication instances when one may already exist from the test class's setUp or a previous test. Refactor to ensure QApplication is instantiated only once per test session or properly manage its lifecycle (e.g., using `QApplication.instance() or QApplication(sys.argv)` in the app, and ensuring tests use a shared instance or clean up properly).
    *   **Source:** `pytest_execution_report.txt`
2.  **Correct type mismatch for `set_eq_values` (list[int] vs list[float]).** (Priority: 2)
    *   **Details:** Ensure data passed to `HeadsetService.set_eq_values` from UI components (e.g., `EqualizerEditorWidget`) is `list[float]`. This may involve casting `int` values to `float` before calling.
    *   **Source:** `mypy_type_checking_report.txt`
3.  **Correct MyPy `assignment` errors (int to bool) in `HeadsetService._get_parsed_status_hid`.** (Priority: 2)
    *   **Details:** Review type inference for `parsed_status` dictionary. Explicitly define its structure with a `TypedDict` to ensure correct type checking for keys like `battery_percent` (likely `Optional[int]`, not `bool`).
    *   **Source:** `mypy_type_checking_report.txt`
4.  **Address all remaining Pytest failures.** (Priority: 2)
    *   **Details:** After fixing the specific issues above, re-run tests and address any other reported failures to ensure the test suite passes.
    *   **Source:** `pytest_execution_report.txt`
5.  **Fix `KeyError: 'release_number'` in `test_headset_service.py` mock data.** (Priority: 2)
    *   **Details:** Mock data for `hid.enumerate()` in `test_connect_device_fails_all_attempts_calls_create_rules` and `test_connect_device_success_does_not_call_create_rules` is missing the `release_number` key. Update mock data to include this key (e.g., `'release_number': 0x0100`).
    *   **Source:** `pytest_execution_report.txt`
6.  **Fix `_create_udev_rules` mock assertion in `test_headset_service.py`.** (Priority: 2)
    *   **Details:** The test `test_connect_device_enumerate_empty_calls_create_rules` fails. Investigate mock setup for `hid.enumerate` returning empty, or logic in `HeadsetService._connect_hid_device` that should call `_create_udev_rules`.
    *   **Source:** `pytest_execution_report.txt`
7.  **Replace `builtins.any` with `typing.Any` in type hints.** (Priority: 3)
    *   **Details:** Correct type hints in UI files (e.g., `equalizer_editor_widget.py`, `system_tray_icon.py`) that incorrectly use `any` instead of `typing.Any`.
    *   **Source:** `mypy_type_checking_report.txt`
8.  **Address MyPy `import-untyped` error for `hid`.** (Priority: 3)
    *   **Details:** Add `# type: ignore[import-untyped]` to the `import hid` line in `headsetcontrol_tray/headset_service.py`. Long-term, consider creating or finding stubs for the `hid` library.
    *   **Source:** `mypy_type_checking_report.txt`
9.  **Fix MyPy `attr-defined` errors for `logger.verbose`.** (Priority: 3)
    *   **Details:** Standard `logging.Logger` has no `verbose` method. Either provide stubs for `verboselogs` that MyPy can see, cast the logger instance, use `getattr(logger, 'verbose', logger.debug)`, or replace `.verbose` calls with `.debug` or appropriate standard levels.
    *   **Source:** `mypy_type_checking_report.txt`
10.  **Resolve MyPy import errors in `test_headset_service.py`.** (Priority: 3)
    *   **Details:** Adjust `sys.path` modifications or import statements in `headsetcontrol_tray/tests/test_headset_service.py` to ensure MyPy can correctly find and parse the `headset_service` module and avoid redefinition errors.
    *   **Source:** `mypy_type_checking_report.txt`
11.  **Address MyPy `import-untyped` error for `verboselogs`.** (Priority: 4)
    *   **Details:** Add `# type: ignore[import-untyped]` to the `import verboselogs` line in `headsetcontrol_tray/__main__.py`. Consider minimal stubs if `verbose` and other levels are widely used.
    *   **Source:** `mypy_type_checking_report.txt`
12.  **Complete manual fixes for remaining Ruff linting errors.** (Priority: 4)
    *   **Details:** Manually address any `E701`, `E702` (multiple statements on one line), `E741` (ambiguous variable name), and other errors reported by `ruff check .` that were not auto-corrected by `ruff --fix`. Refer to `ruff_linting_report.txt` and previous interactive fixing logs.
    *   **Source:** `ruff_linting_report.txt`
13.  **Decompose complex private methods in `HeadsetService` (e.g., `_connect_hid_device`).** (Priority: 5)
    *   **Details:** Break down `_connect_hid_device` and `_get_parsed_status_hid` into smaller, more focused private methods for better readability and testability.
    *   **Source:** `comprehensive_code_review_report.md`
14.  **Refactor `HeadsetService` fallback logic to reduce duplication.** (Priority: 5)
    *   **Details:** Implement a helper method or decorator in `HeadsetService` to encapsulate the common 'try HID, then fallback to CLI' pattern.
    *   **Source:** `comprehensive_code_review_report.md`