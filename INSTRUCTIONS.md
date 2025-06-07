# INSTRUCTIONS.md - Python Project Rules for LLM Agents

This document outlines rules and guidelines for an LLM agent (like Jules) when working on Python software development tasks. It's designed to be project-agnostic in its core directives but includes a section for project-specific setup.

## 1. Project-Specific Configuration & Setup

*   **Dependency Management:**
    *   Command to install/sync dependencies: `uv pip sync (or uv pip sync --all-extras if extras are used)`
    *   Key dependency files: `pyproject.toml, uv.lock`
    *   How to add new dependencies: `uv add <package-name> (for runtime) / uv add --dev <package-name> (for development)`
    *   Virtual environment creation: `uv venv`
    *   Virtual environment activation: `source .venv/bin/activate (Linux/macOS) or .venv\Scripts\activate (Windows)`
*   **Linting & Static Analysis:**
    *   Command to run linters (e.g., Flake8, Ruff): `ruff check . --fix`
    *   Command to run static type checker (e.g., MyPy): `mypy headsetcontrol_tray/ `
    *   Are there specific configuration files for these tools? `pyproject.toml (for ruff), mypy.ini (for mypy)`
*   **Testing:**
    *   Command to run all tests: `pytest`
    *   Command to run specific tests: `pytest headsetcontrol_tray/tests/test_app.py::TestClassName::test_method_name`
    *   Testing framework used: `pytest`
    *   Are there specific test coverage requirements or tools? `pytest-cov (after installing with uv add --dev pytest-cov)`
*   **Running the Project (if applicable):**
    *   Command to run the main application/service: `python -m headsetcontrol_tray (or using uv: uv run python -m headsetcontrol_tray)`
*   **Project Style Guide (if distinct from general PEP8):**
    *   Link to or summary of project-specific style nuances: `Primarily PEP 8, enforced by Ruff/Black. Specific nuances TBD.`

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

## Structurizr DSL Notes

When defining elements in your `workspace.dsl` file, pay close attention to the syntax specified in the Structurizr DSL documentation.

### `person` Element Syntax

A common element is `person`, which defines a user or role. The correct syntax is:

`person <name> [description] [tags]`

Where:
- `<name>`: The name of the person (e.g., "Admin User"). This is a required field.
- `[description]`: An optional description of the person, enclosed in double quotes (e.g., "An administrator responsible for system configuration.").
- `[tags]`: Optional tags, enclosed in double quotes (e.g., "Internal, Privileged"). If no specific tags are needed beyond the defaults, you can use an empty string `""` or omit the tags part if no description is also provided.

**Example of a parsing error to avoid:**
Incorrect: `user = person "User" "A description." "" "ExtraToken"` (This has too many tokens)
Correct:   `user = person "User" "A description." ""` (No extra tags)
Correct:   `user = person "User" "A description." "Tag1, Tag2"` (With specific tags)
Correct:   `user = person "User" "A description."` (Description provided, no specific tags beyond default)
Correct:   `user = person "User"` (Name only, no description or specific tags beyond default)

The parser is sensitive to the number of quoted strings (tokens) provided for each element type.

### `softwareSystem` Element Syntax

Another common element is `softwareSystem`. The correct syntax is:

`softwareSystem <name> [description] [tags]`

Where:
- `<name>`: The name of the software system (e.g., "Payment Gateway"). Required.
- `[description]`: An optional description, in double quotes.
- `[tags]`: Optional tags, in double quotes (e.g., "External, Critical"). If you want to specify a type like "Application" or "Software/Firmware" as a tag, it should be the content of this tags string.

**Example of a parsing error to avoid:**
Incorrect: `mySystem = softwareSystem "My System" "A description." "" "SystemTypeTag"` (This has too many tokens)
Correct:   `mySystem = softwareSystem "My System" "A description." "SystemTypeTag"` (SystemTypeTag is the tag)
Correct:   `mySystem = softwareSystem "My System" "A description." "Tag1, Tag2"`
Correct:   `mySystem = softwareSystem "My System" "A description."`
Correct:   `mySystem = softwareSystem "My System"`

Note: Unlike `container` elements, the `softwareSystem` definition does not have a separate `[technology]` field in its main definition line. Technology or type information should typically be included as a tag.

### Element Style Inheritance

When defining element styles in the `styles` block, it's important to note that the `inherits` keyword is **not** a valid property within an `element "Tag" { ... }` definition.

Instead, style inheritance and combination are typically handled by Structurizr based on the tags an element possesses:

1.  **Base Styles**: Define base styles for general tags like "Person" or "Software System".
    ```dsl
    styles {
        element "Software System" {
            background #1168bd
            color #ffffff
            shape RoundedBox
        }
        element "Person" {
            background #08427b
            color #ffffff
            shape Person
        }
    }
    ```

2.  **Specific Styles**: For elements that have more specific characteristics (and corresponding tags), define additional styles for those specific tags. These styles will be layered on top of or override the base styles.
    ```dsl
    styles {
        // Base style for all software systems
        element "Software System" {
            shape RoundedBox
            background #dddddd
        }

        // Specific style for elements also tagged "Application"
        element "Application" {
            // This element will get shape and background from "Software System"
            // and then this icon will be added/applied.
            icon "https://static.structurizr.com/icons/desktop-24.png"
        }
    }
    ```

3.  **Element Tagging**: Ensure your model elements are tagged appropriately. An element can have multiple tags.
    ```dsl
    model {
        myWebApp = softwareSystem "My Web App" "Serves web content." "Application"
        // myWebApp has tags: "Software System" (default), "Element" (default), and "Application"
    }
    ```
    In the example above, `myWebApp` would receive base styling from the "Software System" tag style and then have the "Application" tag style (e.g., the icon) applied.

**Incorrect usage (causes parsing error):**
```dsl
element "Application" {
    inherits "Software System" // This is invalid
    icon "..."
}
```

By defining styles for individual tags and ensuring elements have all relevant tags, the Structurizr renderer will combine these styles appropriately.

### Defining Containers and Container Views

To visualize the internal structure of a `softwareSystem`, you define `container` elements within it and then create a `containerView` to display them.

1.  **Define Containers within a Software System**:
    Expand your `softwareSystem` definition into a block and add `container` elements.
    ```dsl
    model {
        mySystem = softwareSystem "My System" "An example system." "InternalApp" {
            myDatabase = container "My Database" "Stores system data." "SQL Database" "Database"
            myApi = container "My API" "Provides access to data." "Java/Spring" "API"

            // Define relationships between containers or to other elements
            myApi -> myDatabase "Reads/Writes"
            // If 'user' is an external element (e.g., a person)
            // user -> myApi "Uses API"
        }
    }
    ```
    - Each `container` has a name, description, technology (optional), and tags (optional).

2.  **Define a Container View**:
    In the `views` block, add a `container` view (often referred to as `containerView` in documentation but keyword is `container` for the view type) targeting your software system.
    ```dsl
    views {
        // ... other views (systemContext, etc.)
        container mySystem "MySystemContainers" "Container diagram for My System." {
            include * // Includes all containers and relevant external elements
            // You can also specify particular containers: include myApi, myDatabase
            // And people/software systems connected to them: include user
            autoLayout
        }
        // ... styles ...
    }
    ```
    - The first argument to `container` (for a view) is the identifier of the software system.
    - The `include *` directive is a common way to show all containers within that system and the elements connected to them.

### Element Definition Order

To avoid "element does not exist" parsing errors when defining relationships, it's generally a good practice to define elements (like people, software systems, containers) before they are referenced. The Structurizr DSL parser may not always look ahead to find definitions that appear later in the file.

**Example:**

If `SystemB` is defined after `SystemA`, and `SystemA` tries to form a relationship with `SystemB`:

```dsl
// Potentially problematic order
model {
    systemA = softwareSystem "System A" {
        -> systemB "Uses" // systemB might not be found yet
    }
    systemB = softwareSystem "System B"
}
```

**Recommended Order:**

```dsl
model {
    systemB = softwareSystem "System B" // Define systemB first
    systemA = softwareSystem "System A" {
        -> systemB "Uses" // Now systemB is known
    }
}
```
This is particularly relevant when an element (e.g., a container inside `SystemA`) references another top-level element (e.g., `SystemB`).

### Relationship Specificity and Redundancy

Structurizr creates implicit relationships. For example, if you define a relationship from a `Person` to a `Container` within a `SoftwareSystem` (e.g., `user -> MyWebAppClient`), Structurizr understands that the `user` is also implicitly related to the parent `MyWebApp` software system.

Because of this, defining both a specific relationship (e.g., `user -> MyWebAppClient`) and a more general one (e.g., `user -> MyWebApp`) can sometimes lead to "relationship already exists" errors.

**General Guideline:**
Prefer defining the most specific relationship. For example, if a user interacts directly with a specific container (like a GUI client or an API), define the relationship to that container.

```dsl
model {
    user = person "User"
    mySystem = softwareSystem "My System" {
        myClient = container "My Client" "GUI for My System." "Desktop App"

        // Specific relationship (Preferred)
        user -> myClient "Uses the client"
    }

    // This might be redundant if the above is defined,
    // as user's interaction with myClient implies interaction with mySystem.
    // user -> mySystem "Uses My System"
}
```
If a general relationship to the software system is still needed for clarity in a higher-level diagram (like System Context) and a specific one for a lower-level diagram (like Container), ensure their descriptions or technologies are distinct enough if you choose to keep both. However, often the specific relationship is sufficient, and Structurizr will render it appropriately in parent diagrams.
```
