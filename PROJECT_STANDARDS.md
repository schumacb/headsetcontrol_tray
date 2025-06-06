# Proposal for ProjectStandards.md Document

This document outlines a proposal for creating and maintaining a `ProjectStandards.md` (or `DEVELOPMENT_STANDARDS.md`) file for the SteelSeries Arctis Nova 7 Tray Utility project.

## 1. Purpose of the Document

A `ProjectStandards.md` document serves as a central reference for developers contributing to the project. Its primary benefits include:

*   **Consistency:** Ensures that all code contributed to the project follows a consistent style, set of practices, and architectural principles. This improves readability and predictability.
*   **Onboarding:** Helps new contributors get up to speed quickly by providing a clear guide to how the project is built and what is expected of their contributions.
*   **Quality:** Promotes higher code quality by explicitly stating best practices for error handling, testing, logging, etc.
*   **Decision Record:** Acts as a record for key design decisions and their rationale, preventing repeated discussions and providing context for future development.
*   **Maintainability:** A shared understanding of standards makes the codebase easier to maintain and evolve over time.

## 2. Suggested Document Structure (Table of Contents)

1.  **Introduction**
    *   Purpose of this document.
    *   Link to project goals (if any explicitly stated).
    *   Emphasis on this being a living document.
2.  **Core Architectural Principles**
    *   Brief overview of the application's architecture (e.g., Layered, MVP-like).
    *   Key components and their primary responsibilities (e.g., `HeadsetService` for hardware abstraction, `ConfigManager` for settings, `SystemTrayIcon` for UI).
    *   Importance of maintaining separation of concerns.
3.  **Coding Style**
    *   PEP 8 as the baseline.
    *   Auto-formatter (e.g., Black or Ruff Formatter) and its configuration (e.g., line length).
    *   Import organization (grouping, sorting with `isort` or formatter).
    *   Docstring conventions (style, what to document).
    *   Inline comment guidelines.
    *   Type hinting conventions (mandatory for new code, striving for specificity).
4.  **Error Handling Philosophy**
    *   Emphasis on specific exception handling.
    *   Guidelines for logging errors (including stack traces for unexpected issues).
    *   Policy on custom exceptions (use if they significantly clarify error types for callers).
    *   Contextual application of Fail Fast vs. Graceful Degradation.
    *   Resource cleanup on error.
5.  **Logging Practices**
    *   Standard log levels and their intended use (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    *   Clarification on `logger.verbose` (standardize or replace).
    *   What to log: key operations, decisions, state changes, errors, warnings.
    *   Avoiding sensitive information in logs.
6.  **Testing Strategy**
    *   Requirement for unit tests for new features and bug fixes.
    *   Focus areas for testing (e.g., `HeadsetService` logic, `ConfigManager` I/O, complex UI logic).
    *   Aim for good code coverage, but prioritize meaningful tests over raw numbers.
    *   Principles for writing tests (independence, repeatability, clarity).
7.  **Dependency Management**
    *   Process for adding or updating dependencies (e.g., update `pyproject.toml`, regenerate lock file).
    *   Preference for minimizing dependencies.
    *   Schedule or triggers for reviewing and updating dependencies (security, bug fixes).
8.  **Commit Message Style**
    *   Chosen standard (e.g., Conventional Commits, or a defined subject/body format).
    *   Emphasis on clear, concise, and informative messages.
9.  **Code Review Process** (If applicable, e.g., for multiple contributors or open-source model)
    *   Steps for submitting code for review.
    *   Key areas to check during reviews (adherence to standards, correctness, etc.).
    *   Process for addressing feedback.
10. **Key Design Decisions Register**
    *   A section to document important architectural or implementation decisions and their rationale.
    *   Examples:
        *   "Why the HID/CLI fallback mechanism in `HeadsetService`?"
        *   "Rationale for choosing JSON for configuration files."
        *   "Decision on adaptive polling in `SystemTrayIcon`."
11. **Modularity and Refactoring Guidelines**
    *   Encouragement for ongoing refactoring of complex or duplicated code.
    *   Reiteration of the Single Responsibility Principle when adding new code.
    *   Preference for configuration (`app_config.py`) over hardcoded values in logic.
12. **How to Update This Document**
    *   Process for proposing changes or additions to these standards (e.g., via discussion, pull request).

## 3. Key Content Points for Each Section (Examples)

*   **Core Architectural Principles:**
    *   "Application follows a layered architecture (Presentation, Service, Data) with MVP-like patterns in the UI."
    *   "`HeadsetService` abstracts all hardware communication."
    *   "`app_config.py` is the single source for static device and application data."
*   **Coding Style:**
    *   "PEP 8 is mandatory. Use Black with line length 100."
    *   "Imports: stdlib, then third-party, then local, sorted alphabetically."
    *   "Docstrings for all public modules, classes, functions. Type hints for all signatures."
*   **Error Handling Philosophy:**
    *   "Catch specific exceptions. Log all caught exceptions, with `exc_info=True` for unexpected ones."
    *   "Fail fast for critical startup/config errors. Gracefully degrade for non-essential feature failures."
*   **Logging Practices:**
    *   "DEBUG for dev trace, INFO for user actions/app state, WARNING for recoverable issues, ERROR for functional failures."
    *   "Ensure `verboselogs` is properly integrated if `logger.verbose` is to be used."
*   **Testing Strategy:**
    *   "New code requires tests. Focus on `HeadsetService` logic and critical UI paths."
    *   "Tests must be runnable independently."
*   **Dependency Management:**
    *   "Update `pyproject.toml` for changes; run `uv pip compile pyproject.toml -o requirements.txt` (or equivalent for chosen tool) to update lock."
    *   "Review dependencies quarterly for updates/vulnerabilities."
*   **Commit Message Style:**
    *   "Use Conventional Commits: `feat: Add new sidetone control via HID` or `fix: Resolve incorrect battery parsing`."
*   **Key Design Decisions Register:**
    *   "HID/CLI Fallback: Chosen for robustness and to allow progressive HID implementation while maintaining functionality via `headsetcontrol`."
*   **Modularity and Refactoring:**
    *   "Actively refactor methods longer than X lines or with nesting deeper than Y."
    *   "When adding to a class, verify it still primarily has one reason to change."

## 4. Emphasis on Living Document

The `ProjectStandards.md` should explicitly state that it is a **living document**. It should be reviewed periodically and updated as the project evolves, new tools are adopted, or better practices are identified by the development team. Changes to the standards should be discussed and agreed upon by contributors.

This proposal provides a solid foundation for creating a comprehensive `ProjectStandards.md` document that will benefit the project's long-term health and development efficiency.
