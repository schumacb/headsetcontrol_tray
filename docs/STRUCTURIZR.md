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

This also applies to system-to-system relationships. If a container within `SystemA` has a defined relationship to `SystemB`, an explicit top-level relationship `SystemA -> SystemB` might be flagged as redundant by the parser.

**Example:**

```dsl
model {
    systemA = softwareSystem "System A" {
        containerA1 = container "Container A1"

        // Specific relationship from a container in SystemA to SystemB
        containerA1 -> systemB "Sends data to"
    }
    systemB = softwareSystem "System B"

    // This model-level relationship might be redundant due to the specific one above.
    // systemA -> systemB "Interacts with"
}
```
It's often best to rely on the most specific relationship (e.g., from `containerA1` to `systemB`), as this accurately reflects the interaction point and implies the broader system-level interaction.
```
