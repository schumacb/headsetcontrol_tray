# Recommended Development Guidelines

This document provides development guidelines for the SteelSeries Arctis Nova 7 Tray Utility project, based on a comprehensive code review. Adhering to these guidelines will help improve code quality, maintainability, and collaboration.

## 1. Coding Style

*   **PEP 8 Adherence:**
    *   Strictly follow PEP 8, Python's official style guide. This includes naming conventions (PascalCase for classes, snake_case for functions/variables, UPPER_CASE for constants), code layout, and whitespace.
    *   **Current State:** Generally good, with minor areas for improvement (e.g., occasional long lines, a few redundant assignments noted in the static analysis).
*   **Auto-formatter:**
    *   **Recommendation:** Adopt and consistently use an auto-formatter like **Black** or **Ruff Formatter**. This will enforce uniform style, reduce cognitive load from formatting discussions, and handle most PEP 8 layout rules automatically. Configure it with a reasonable line length (e.g., 88 or 100 characters).
*   **Line Length:**
    *   Aim for a maximum line length as configured by the auto-formatter (e.g., 88 or 100 characters) to improve readability. Long f-strings or complex data structures should be broken down if they exceed this.
*   **Import Organization:**
    *   Continue the current good practice of grouping imports:
        1.  Standard library imports.
        2.  Third-party library imports.
        3.  Local application imports (using relative imports like `from . import ...`).
    *   Use an import sorter, often included with formatters like Black or available as a separate tool (e.g., `isort`), to keep imports alphabetically sorted within their groups.
*   **Comments and Docstrings:**
    *   **Docstrings:** Provide clear and concise public docstrings for all modules, classes, public methods, and functions, explaining their purpose, arguments, and return values (if any). Use triple quotes (`"""Docstring goes here."""`).
    *   **Inline Comments:** Use inline comments (`#`) to explain non-obvious logic, complex workarounds, or important decisions. Avoid comments that merely restate what the code does.
    *   **TODOs/FIXMEs:** Use `TODO:` or `FIXME:` prefixes for items that need future attention, and consider linking them to issue tracker items.
    *   **Cleanup:** Regularly remove obsolete commented-out code.
*   **Type Hinting Conventions:**
    *   Continue and expand the excellent use of type hints for all function/method signatures (arguments and return types) and important variables.
    *   Use specific types where possible (e.g., `Callable[[], None]` instead of `Any` for a simple callback, `TypedDict` for dictionary structures with known keys) rather than overly generic types like `Any` or `Dict` without parameters.
    *   Utilize `Optional[X]` for values that can be `None`.
    *   Use `from typing import ...` to import necessary types.

## 2. Error Handling

*   **Specificity of Exceptions:**
    *   Catch specific exceptions rather than using a bare `except:` or overly broad `except Exception:`. This allows for more targeted error handling and avoids masking unexpected issues.
    *   **Current State:** Generally good, with specific exceptions like `FileNotFoundError`, `subprocess.CalledProcessError`, `json.JSONDecodeError` being caught.
*   **Logging Errors:**
    *   Always log caught exceptions with sufficient context (e.g., using `logger.error("Failed to do X: %s", e, exc_info=True)` or similar to include stack traces for unexpected errors).
*   **Custom Exceptions:**
    *   Consider defining custom exceptions for application-specific error conditions if it improves clarity and allows callers to handle specific application errors more effectively. For example, `HidCommunicationError` or `CliToolError` could be possibilities if more granular error handling by callers is desired beyond boolean return codes. Currently, the return value pattern (`Optional[X]`, `bool`) is used effectively.
*   **Graceful Degradation vs. Fail-Fast:**
    *   **Fail Fast Early:** For critical startup conditions (e.g., udev rules, missing essential dependencies like `pkexec`), continue the current practice of failing fast by promptly informing the user and/or logging critical errors.
    *   **Graceful Degradation:** For non-critical features or when fallbacks exist (e.g., HID vs. CLI), allow the application to run with reduced functionality. Clearly log warnings when features are unavailable or a fallback is used. If a user attempts to use a degraded feature, provide clear UI feedback if possible.
    *   **Resource Management:** Continue closing resources (like HID device handles) promptly when errors indicate they are no longer valid.

## 3. Logging Practices

*   **Consistent Log Levels:**
    *   `DEBUG`: For detailed diagnostic information useful for developers (e.g., HID report contents, specific function call sequences).
    *   `INFO`: For high-level application lifecycle events, user-driven actions, and significant successful operations.
    *   `VERBOSE` (if kept): Standardize its usage. If `verboselogs` is used, ensure it's explicitly configured in `app.py`. Otherwise, migrate these logs to `DEBUG` and use specific conditions or logger names if fine-grained control is needed.
    *   `WARNING`: For recoverable issues, unexpected conditions that don't immediately break functionality, or when falling back to less optimal behavior (e.g., CLI fallback).
    *   `ERROR`: For significant errors that prevent a specific operation or functionality from working correctly.
    *   `CRITICAL`: For errors that may lead to application termination or make the application unstable.
*   **Log Content:**
    *   Logs should be informative and provide context. Include relevant variable values where appropriate, but be mindful of sensitive data.
    *   Ensure log messages clearly indicate the component or module they originate from (current logger naming convention already supports this).
*   **Startup Logging:** Continue logging key startup information, such as `headsetcontrol` availability and initial device connection status.

## 4. Dependency Management

*   **`pyproject.toml` and `uv.lock`:**
    *   Keep `pyproject.toml` (listing direct dependencies and project metadata) accurate and up-to-date.
    *   Regularly regenerate `uv.lock` (or `poetry.lock` / `requirements.txt` if using other tools) to ensure reproducible builds and capture transitive dependencies.
*   **Minimizing Dependencies:**
    *   Evaluate new dependencies carefully to avoid unnecessary bloat. Prefer standard library solutions where feasible.
*   **Regular Review:**
    *   Periodically review dependencies for security vulnerabilities (e.g., using `piprot` or GitHub's Dependabot) and update them as appropriate to get bug fixes and new features, while being mindful of breaking changes.

## 5. Testing

*   **Importance:** Recognize that a comprehensive test suite is crucial for long-term maintainability, enabling safe refactoring and reliable feature additions.
*   **New Features and Bug Fixes:** All new functionality should be accompanied by unit tests. Bug fixes should include regression tests to prevent the issue from recurring.
*   **Focus Areas:**
    *   Prioritize testing for `HeadsetService` (HID/CLI logic, parsing, fallbacks).
    *   Test `ConfigManager` for loading/saving configurations and handling defaults.
    *   For UI components like `SystemTrayIcon`, unit test specific logic within methods where possible. Consider higher-level UI tests if the framework allows and complexity warrants.
*   **Test Characteristics:** Tests should be independent (not relying on the state of other tests) and repeatable (producing the same results every time they are run).
*   **Code Coverage:** While not a silver bullet, aim for a reasonable level of code coverage as an indicator, but focus more on testing critical paths and edge cases.

## 6. Commit Messages

*   **Standard Format:**
    *   **Recommendation:** Adopt a standard commit message format like [Conventional Commits](https://www.conventionalcommits.org/). This improves history readability and can automate changelog generation.
    *   **Alternative:** If Conventional Commits is too heavy, a simple standard:
        *   A short, imperative subject line (e.g., "Fix: Correct battery level parsing for HID").
        *   A blank line followed by a more detailed body if necessary.
*   **Clarity and Conciseness:** Messages should clearly explain the *what* and *why* of the change.

## 7. Code Reviews

*   **Practice:** If working in a team or accepting contributions, conduct code reviews for all new code.
*   **Focus:** Reviews should check for adherence to these guidelines, correctness, performance, security, and overall code quality.
*   **Constructive Feedback:** Reviews should be constructive and aim to improve the codebase and share knowledge.

## 8. Modularity and Refactoring

*   **Continuous Refactoring:**
    *   **Recommendation:** Embrace continuous refactoring. Regularly revisit and improve existing code, especially complex areas identified in reviews (e.g., long methods in `HeadsetService` or `SystemTrayIcon`, duplicated logic in `HeadsetService` fallbacks).
    *   Use the test suite as a safety net during refactoring.
*   **Adhering to SRP:**
    *   When adding new functionality or modifying existing code, be mindful of the Single Responsibility Principle. If a class or method starts doing too many unrelated things, consider breaking it down.
*   **Configuration over Code:** Continue leveraging `app_config.py` for device-specific details and application defaults rather than hardcoding these values in logic-heavy modules.

By following these guidelines, the project can maintain a high standard of code quality, making it easier to understand, modify, and extend in the future.
