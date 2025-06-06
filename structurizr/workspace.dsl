workspace "HeadsetControl System" "A system for managing and controlling a headset." {

    model {
        user = person "User" "A person using the headset."
        headset = softwareSystem "Headset" "The physical headset device." "External"

        headsetControlTray = softwareSystem "HeadsetControl Tray" "Provides user interface and control for the headset." {
            tags "HeadsetControl"

            trayApplication = container "Tray Application" "Main GUI application for user interaction." "Python, PySide6" {
                tags "GUI"
                systemTrayIcon = component "System Tray Icon" "UI element for quick access to headset features and settings." "PySide6"
                settingsUI = component "Settings UI" "Dialog for managing application and headset configurations." "PySide6"
                equalizerUI = component "Equalizer UI" "Interface for adjusting headset equalizer presets." "PySide6"
                chatMixUI = component "ChatMix UI" "Interface for adjusting headset chatmix." "PySide6"
            }

            headsetService = container "Headset Service" "Handles communication with the headset." "Python, headsetcontrol CLI / raw HID" {
                tags "Service"
                headsetControlCLIWrapper = component "HeadsetControl CLI Wrapper" "Interacts with the 'headsetcontrol' command-line tool." "Python subprocess"
                hidCommunicationHandler = component "HID Communication Handler" "(Future capability) Directly communicates with the headset via HID reports." "Python HID library"
                devicePoller = component "Device Poller" "Periodically checks headset status (e.g., battery, connection)." "Python"
            }

            configurationManager = container "Configuration Manager" "Manages application and headset settings." "Python" {
                tags "Configuration"
                configFileRW = component "Config File R/W" "Reads and writes configuration data from/to a file." "Python, JSON/INI"
            }

            // Relationships
            user -> trayApplication "Interacts with"
            trayApplication -> headsetService "Uses" "Controls headset and retrieves status"
            trayApplication -> configurationManager "Uses" "Loads and saves settings"
            headsetService -> headsetControlCLIWrapper "Uses" "Interacts with Headset"
            headsetService -> hidCommunicationHandler "Uses" "Interacts with Headset (Future)"
            headsetService -> headset "Interacts with" "Sends commands and receives status"
            configurationManager -> configFileRW "Uses" "Persists settings"
        }
    }

    views {
        systemContext headsetControlTray "SystemContext" "System Context diagram for HeadsetControl Tray" {
            include *
            autoLayout
        }

        container headsetControlTray "Containers" "Container diagram for HeadsetControl Tray" {
            include *
            autoLayout
        }

        component trayApplication "TrayApplicationComponents" "Component diagram for Tray Application" {
            include *
            autoLayout
        }

        component headsetService "HeadsetServiceComponents" "Component diagram for Headset Service" {
            include *
            autoLayout
        }

        component configurationManager "ConfigurationManagerComponents" "Component diagram for Configuration Manager" {
            include *
            autoLayout
        }

        styles {
            element "Software System" {
                background #1168bd
                color #ffffff
            }
            element "Container" {
                background #438dd5
                color #ffffff
            }
            element "Component" {
                background #85cbf0
                color #000000
            }
            element "Person" {
                shape Person
                background #08427b
                color #ffffff
            }
            element "External" {
                background #999999
                color #ffffff
            }
            element "GUI" {
                shape WebBrowser
            }
            element "Service" {
                shape Cog
            }
            element "Configuration" {
                shape Folder
            }
            element "HeadsetControl" {
                shape MobileDevicePortrait // Closest to a headset icon
            }
        }
    }
}
