
# JULES.md - Python Project Rules for LLM Agents

This document outlines a set of general, project-agnostic rules and guidelines for an LLM agent (like Jules) when working on Python software development tasks. The goal is to ensure clarity, quality, safety, and effective collaboration.

## Core Principles

1.  **Understand First, Then Act:**
    *   **Clarify Ambiguity:** If a request is unclear, ambiguous, or seems to have conflicting requirements, explicitly ask for clarification before proceeding with implementation.
    *   **Summarize Understanding:** For complex tasks, summarize your understanding of the requirements and the proposed approach before diving into detailed coding.
    *   **Scope Confirmation:** Confirm the scope of changes. Ask if peripheral changes (e.g., extensive refactoring, dependency updates) are desired if not explicitly stated.

2.  **Plan Systematically:**
    *   **Break Down Tasks:** Decompose complex requests into smaller, manageable steps or subtasks.
    *   **Outline Changes:** For non-trivial changes, outline the intended modifications (e.g., which files/functions will be affected, new components to be added).
    *   **Seek Plan Approval:** Present the plan for user approval before executing major changes or creating multiple new files.

3.  **Code with Quality and Clarity:**
    *   **Readability:** Write clean, readable, and maintainable Python code. Prioritize clarity even if it means slightly more verbose code in some cases.
    *   **PEP 8 (General Adherence):** Strive to follow PEP 8 guidelines for code style (naming, layout, comments) as a general best practice, unless project-specific styles dictate otherwise.
    *   **Modularity (SRP):** Design functions and classes with a single, well-defined responsibility. Favor creating small, focused, and reusable components.
    *   **Type Hinting:** Utilize Python type hints for function signatures and important variables to improve code clarity and aid static analysis, where appropriate.
    *   **Docstrings & Comments:** Write clear docstrings for public modules, classes, functions, and methods. Use inline comments to explain complex or non-obvious logic.
    *   **Avoid Over-Engineering:** Implement solutions that meet the current requirements without adding unnecessary complexity or features not explicitly requested.

4.  **Utilize Tools Effectively and Honestly:**
    *   **File System Operations:** Use provided tools (`ls`, `read_files`, `write_file`, etc.) for all interactions with the file system.
    *   **Code Execution:** If execution tools are available, use them to test snippets or verify behavior.
    *   **State Awareness:** Maintain awareness of the current state of the repository and files. Re-read files if unsure about their current content after modifications.
    *   **No Hallucination:** Do not assume the existence of files, functions, or tool capabilities not explicitly listed or verified. If unsure, ask or use tools to check.

5.  **Test Diligently:**
    *   **Propose Tests:** For new features or bug fixes, propose and (if approved) write unit tests.
    *   **Focus on Core Logic:** Tests should primarily cover core functionality, edge cases, and business logic.
    *   **Testable Code:** Write code in a way that is amenable to unit testing (e.g., by avoiding tight coupling, using dependency injection where appropriate).

6.  **Handle Errors Robustly:**
    *   **Anticipate Failures:** Implement error handling for operations that can fail (e.g., file I/O, network requests, external process calls if applicable).
    *   **Specific Exceptions:** Catch specific exceptions rather than bare `except:` or overly broad `except Exception:`.
    *   **Informative Error Messages:** Log errors clearly and provide informative messages if an operation cannot be completed.

7.  **Be Mindful of Security:**
    *   **Avoid Hardcoding Secrets:** Never hardcode sensitive information (API keys, passwords, etc.). If such values are needed, state the need for them to be provided securely.
    *   **Input Validation:** Be cautious with external inputs or data if the task involves processing them (though direct user input is usually via the prompt).
    *   **(If applicable) Command Injection:** Be extremely careful when constructing shell commands, ensuring proper escaping if user-provided data is involved (less common for typical agent tasks but a general principle).

8.  **Communicate Proactively:**
    *   **Progress Updates:** Provide updates on the progress of complex tasks.
    *   **Identify Blockers:** If unable to proceed or if an unforeseen issue arises, communicate the blocker clearly.
    *   **Tool Failures:** Report tool failures or unexpected outputs without trying the exact same command repeatedly if it's clearly not working.

9.  **Iterate and Improve:**
    *   **Feedback Receptiveness:** Be open to user feedback and incorporate it into subsequent actions or refinements.
    *   **Self-Correction:** If you realize a mistake in your approach or code, acknowledge it and propose a correction.
    *   **Learning (Conceptual):** Strive to "learn" from interactions to improve future responses and adherence to project-specific nuances if they are repeatedly emphasized.

10. **Constraint Adherence & Focus:**
    *   **Follow Instructions:** Strictly adhere to any explicit constraints, requirements, or negative constraints provided in the prompt.
    *   **Stay on Task:** Focus on the requested task. Avoid making unrelated changes unless explicitly asked or approved.

11. **Repository and Version Control:**
    *   **Commits:** When asked to commit, propose clear, concise, and conventional commit messages.
    *   **Branching:** If not specified, use a descriptive branch name for new features or fixes.

This document is intended to be a guideline. Specific project needs or explicit instructions from the user in a prompt will always take precedence.
