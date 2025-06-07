workspace "HeadsetControl Architecture" "Describes the architecture of the HeadsetControl system and its related components." {

    model {
        user = person "User" "A person using the HeadsetControl Tray application to manage their headset settings." ""
        headsetHardware = softwareSystem "Headset Hardware/Firmware" "The physical headset device and its embedded firmware." "Software/Firmware"
        headsetControlTray = softwareSystem "HeadsetControl Tray" "A tray application that allows users to manage their headset settings and view status information." "Application" {
            hcTrayProcess = container "HeadsetControl Tray Process" "The main application process for the headset control tray." "Python" "Monolith" {
                # Define components within hcTrayProcess
                uiComponent = component "UI Component" "Handles user interface logic, displays information, and captures user input." "Python/Qt" "GUI Logic"
                configComponent = component "Configuration Component" "Manages loading, saving, and applying application settings and headset profiles." "Python" "Settings Management"
                headsetDriverComponent = component "Headset Driver Component" "Interfaces directly with the headset hardware via OS APIs." "Python" "Device Interface"

                # Define relationships between these components
                uiComponent -> configComponent "Uses" "Loads/Saves settings"
                uiComponent -> headsetDriverComponent "Uses" "Sends commands/gets status"

                # Define how these components interact with elements outside this container
                # This makes the container-level relationships (user -> hcTrayProcess and hcTrayProcess -> headsetControl) potentially redundant
                user -> uiComponent "Interacts with"
                headsetDriverComponent -> headsetHardware "Communicates with" "Sends commands/receives status via OS APIs"
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
