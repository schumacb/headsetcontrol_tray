workspace "HeadsetControl Architecture" "Describes the architecture of the HeadsetControl system and its related components." {

    model {
        user = person "User" "A person using the HeadsetControl Tray application to manage their headset settings." ""
        headsetControl = softwareSystem "HeadsetControl" "The core software/firmware responsible for managing the headset's functions, settings, and communication." "Software/Firmware"
        headsetControlTray = softwareSystem "HeadsetControl Tray" "A tray application that allows users to manage their headset settings and view status information." "Application" {
            hcTrayProcess = container "HeadsetControl Tray Process" "The main application process for the headset control tray." "Python" "Monolith" {
                # Define components within hcTrayProcess
                uiComponent = component "UI Component" "Handles user interface logic, displays information, and captures user input." "Python/Qt" "GUI Logic"
                configComponent = component "Configuration Component" "Manages loading, saving, and applying application settings and headset profiles." "Python" "Settings Management"
                headsetDriverComponent = component "Headset Driver Component" "Interfaces with the headsetControl system to send commands and receive status updates." "Python" "Device Interface"

                # Define relationships between these components
                uiComponent -> configComponent "Uses" "Loads/Saves settings"
                uiComponent -> headsetDriverComponent "Uses" "Sends commands/gets status"

                # Define how these components interact with elements outside this container
                # This makes the container-level relationships (user -> hcTrayProcess and hcTrayProcess -> headsetControl) potentially redundant
                user -> uiComponent "Interacts with"
                headsetDriverComponent -> headsetControl "Communicates with" "Sends/Receives low-level commands"
            }
        }

    }

    views {
        systemContext headsetControlTray "SystemContext" "The system context view for the HeadsetControl Tray application." {
            include *
            autoLayout
        }

        container headsetControlTray "ContainerView" "The container view for the HeadsetControl Tray application." {
            include *
            autoLayout
        }

        component hcTrayProcess "ComponentView" "The component view for the HeadsetControl Tray Process." {
            include *
            autoLayout
        }

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
            element "Application" {
                icon "https://static.structurizr.com/icons/desktop-24.png"
            }
            element "Software/Firmware" {
                icon "https://static.structurizr.com/icons/component-24.png"
            }
            element "User" {
            }
        }
    }

}
