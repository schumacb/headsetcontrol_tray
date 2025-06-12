# INSTRUCTIONS.md - Python Project Rules for LLM Agents

This document outlines rules and guidelines for an LLM agent (like Jules) when working on Python software development tasks. It's designed to be project-agnostic in its core directives but includes a section for project-specific setup.

## 1. Project-Specific Configuration & Setup

This project uses `uv` for project and virtual environment management, and a set of scripts to help with development tasks.

### Environment Setup

To set up your local development environment, run the provided setup script:

```bash
bash scripts/setup_dev_env.sh
```
This script will:
1.  Check if `uv` is installed and install it if necessary.
2.  Create a Python virtual environment in `.venv/`.
3.  Activate the virtual environment (for the script's execution; you'll need to activate it in your shell separately).
4.  Install all necessary Python dependencies (including development dependencies) using `uv pip install -e ".[dev]"`.
5.  Attempt to install required system packages (like `python3.10-dev`, `xvfb`, `x11-utils`, `libhidapi-dev`) using `sudo apt-get`. If `sudo` is not available or fails, it will list the packages for manual installation.

After the script completes, activate the virtual environment in your current shell session:

```bash
source .venv/bin/activate
```

### Running the Quality Script

Once your environment is set up and the virtual environment is activated, you can run the quality script to perform checks like linting, type checking, and running tests:

```bash
bash scripts/quality.sh
```
This script is configured to run tests in a headless environment if a display server (like X11) is not detected, so it can be used in various local and CI environments.

---

### Tooling

*   **Dependency Management:**
    *   Command to install/sync dependencies: `uv pip sync (or uv pip sync --all-extras if extras are used)`
    *   Key dependency files: `pyproject.toml, uv.lock`
    *   How to add new dependencies: `uv add <package-name> (for runtime) / uv add --dev <package-name> (for development)`
    *   Virtual environment creation: `uv venv`
    *   Virtual environment activation: `source .venv/bin/activate (Linux/macOS) or .venv\Scripts\activate (Windows)`
*   **Linting & Static Analysis:**
    *   Command to run formatter: `ruff format .` (for applying code style formatting, similar to Black)
    *   Command to run linters: `ruff check . --fix` (for identifying and auto-fixing lint issues)
    *   Command to run static type checker: `uv run mypy .` (preferred method) or `mypy .` (if `uv` is not used for task execution)
    *   Configuration files: `pyproject.toml (for ruff linting, formatting, and isort), mypy.ini (for mypy)`
*   **Code Complexity Analysis:**
    *   Tool: Radon
    *   Purpose: Measures code complexity (e.g., Cyclomatic Complexity, Halstead metrics, Maintainability Index). Helps identify overly complex code that might be hard to maintain or test.
    *   Command to run: `radon cc . -a -s` (for Cyclomatic Complexity with average and summary)
    *   Command for all metrics: `radon mi . -s` (for Maintainability Index) or `radon raw . -s` (for raw metrics).
    *   Configuration: Radon can be configured using a `pyproject.toml` file under `[tool.radon]`, but basic command-line usage is often sufficient.
*   **Dead Code Detection:**
    *   Tool: Vulture
    *   Purpose: Finds unused code (dead code) in Python programs. Helps clean up the codebase by identifying functions, variables, classes, etc., that are defined but not used.
    *   Command to run: `vulture src` (scans the source directory)
    *   Command to run: `vulture tests` (scans the tests directory)
    *   Configuration: Vulture can be configured by whitelisting false positives in a `.vulture_whitelist.py` file or through `pyproject.toml` under `[tool.vulture]`.
*   **Testing:**
    *   Command to run all tests: `uv run pytest` (preferred method) or `pytest` (if `uv` is not used for task execution)
    *   Command to run specific tests: `uv run pytest headsetcontrol_tray/tests/test_app.py::TestClassName::test_method_name` (or using `pytest` directly)
    *   Testing framework used: `pytest`
    *   Are there specific test coverage requirements or tools? `pytest-cov (after installing with uv add --dev pytest-cov)`
*   **Running the Project:**
    *   Command to run the main application/service: `python -m headsetcontrol_tray (or using uv: uv run python -m headsetcontrol_tray)`
*   **Project Style Guide:**
    *   Link to or summary of project-specific style nuances: `Primarily PEP 8, enforced by Ruff.`

---

## Structurizr

This project uses Structurizr for C4 model architecture diagrams.

### For Coding Agents

To view the architecture diagrams:

1.  **Ensure Docker is running.**
2.  **Start the Structurizr Lite container:**
    ```bash
    docker run -it --rm -p 8080:8080 -v $(pwd)/docs/architecture/structurizr:/usr/local/structurizr structurizr/lite
    ```
3.  **Open your browser** and navigate to `http://localhost:8080`.

The `workspace.dsl` file defining the model is located at `docs/architecture/structurizr/workspace.dsl`.

### Common Mistakes & Prevention

*   **Error: `java.io.FileNotFoundException: /usr/local/structurizr/workspace.dsl` (or similar) when starting Docker.**
    *   **Cause:** The volume mount `-v` path is incorrect. The Docker container cannot find the `workspace.dsl` file.
    *   **Prevention:** Ensure you are running the `docker run` command from the root directory of this repository. The path `$(pwd)/docs/architecture/structurizr` must correctly point to the directory containing your `workspace.dsl`.
*   **Diagram not updating after changes to `workspace.dsl`:**
    *   **Cause:** The Structurizr Lite container might not automatically reload changes, or your browser might be caching the old version.
    *   **Prevention:**
        *   Restart the Docker container.
        *   Do a hard refresh in your browser (Ctrl+Shift+R or Cmd+Shift+R).

---

## 2. Core LLM Agent Directives

These are primary rules to follow for all tasks.

1.  **Focused Changes (Minimal Diff):**
    *   Only implement changes directly required by the user's request.
    *   Do **not** perform opportunistic refactoring or optimization of unrelated code. The goal is to keep diffs minimal, focused, and easy to review.
    *   If unrelated issues or potential improvements are identified, mention them as recommendations (with priority/value if possible) rather than implementing them directly.

2.  **Scoped Analysis & Modification:**
    *   When performing linting, static code analysis, or applying fixes based on such tools, **only act on code written or directly modified by you (the AI agent) within the current task.**
    *   Do **not** fix warnings or style issues in existing code that you did not change for the current task, unless explicitly requested by the user.
    *   You may recommend addressing pre-existing issues in unchanged code separately.

3.  **Documentation:**
    *   **Docstrings:** Add or update clear, concise docstrings (PEP 257) for all new or modified public classes, methods, and functions. Explain purpose, arguments, and return values.
    *   **Inline Comments:** Use inline comments sparingly. Only add them if they clarify complex or non-obvious logic that cannot be made clear by good naming and structure.
    *   **No Meta-Comments:** Do **not** add comments that describe your changes (e.g., `# Added this import`, `# Refactored this loop`). Commit messages serve this purpose.

4.  **README.md Updates:**
    *   If your changes affect project setup, features, usage, or external dependencies, update `README.md` accordingly to reflect these changes accurately. The `README.md` should reflect the current state of the Project.

5.  **CODE ANALYSIS**
    *   Perform linting formatting and code analysis before commiting changes.

6.  **Testing:**
    *   **Write/Update Tests:** For new features or bug fixes, always write or update relevant unit tests.
    *   **Testable Code:** Strive to write code that is inherently testable (e.g., favoring pure functions, clear interfaces, dependency injection where appropriate).
    *   **Tests Must Pass:** Before committing or submitting changes, ensure all existing and newly added tests pass. If you cannot make them pass, report the issue.

7.  **Adherence to Core Principles:**
    *   **KISS (Keep It Simple, Stupid):** Favor simple, straightforward solutions over unnecessarily complex ones.
    *   **SOLID:** Apply SOLID principles where appropriate to create maintainable and flexible object-oriented designs.

---

## 3. General LLM Agent Coding Principles

These are broader guidelines for effective operation.

1.  **Understand First, Then Act:**
    *   **Clarify Ambiguity:** If a request is unclear or ambiguous, explicitly ask for clarification.
    *   **Summarize Understanding:** For complex tasks, summarize your understanding of requirements and your proposed approach before coding.

2.  **Plan Systematically:**
    *   **Break Down Tasks:** Decompose complex requests into smaller, manageable steps.
    *   **Outline Changes:** For non-trivial changes, outline intended modifications (files, functions, new components).
    *   **Seek Plan Approval:** Present the plan for user approval before executing major changes.

3.  **Code Quality (General):**
    *   **Readability:** Prioritize readable code through clear naming, logical structure, and appropriate use of whitespace.
    *   **PEP 8 (Foundation):** Use PEP 8 as a baseline for Python code style, but defer to project-specific styles if defined in Section 1.
    *   **Modularity:** Design functions and classes with well-defined responsibilities.
    *   **Type Hinting:** Use Python type hints for function signatures and key variables.
    *   **Avoid Over-Engineering:** Implement what is required; do not add features not explicitly requested.

4.  **Utilize Tools Effectively and Honestly:**
    *   **Adhere to Provided Tools:** Use only the tools explicitly available in your environment.
    *   **File System Operations:** Rely on provided tools (`ls`, `read_files`, `write_file`, etc.) for all file system interactions.
    *   **State Awareness:** Re-read files if unsure about their current content after modifications or if a long time has passed.
    *   **No Hallucination:** Do not assume files, functions, or tool capabilities not verified. Ask or use tools to check.

5.  **Handle Errors Robustly:**
    *   **Anticipate Failures:** Implement error handling for operations prone to failure.
    *   **Specific Exceptions:** Catch specific exceptions.
    *   **Informative Error Messages:** Log errors clearly; provide useful messages if an operation fails.

6.  **Be Mindful of Security:**
    *   **No Hardcoded Secrets:** Never hardcode sensitive information.
    *   **Input Validation (if applicable):** Be cautious with external inputs if the task involves processing them.

7.  **Communicate Proactively:**
    *   **Progress Updates:** Provide updates on complex tasks.
    *   **Identify Blockers:** Clearly communicate any blockers.
    *   **Tool Failures:** Report tool failures without repeatedly trying the same failing command.

8.  **Iterate and Improve:**
    *   **Feedback Receptiveness:** Be open to user feedback for refinement.
    *   **Self-Correction:** If a mistake is realized, acknowledge it and propose a correction.

9.  **Constraint Adherence & Focus:**
    *   **Follow Instructions:** Strictly adhere to explicit constraints and requirements.
    *   **Stay on Task:** Focus on the requested task. Avoid unrelated changes unless approved.

10. **Repository and Version Control:**
    *   **Commits:** Propose clear, concise, and conventional commit messages.
    *   **Branching:** Use descriptive branch names if not specified.

This document is a guideline. Specific project needs or explicit user instructions in a prompt always take precedence.
