workspace "HeadsetControl Architecture" "Describes the architecture of the HeadsetControl system and its related components." {

    model {
        user = person "User" "A person using the HeadsetControl Tray application to manage their headset settings." ""
        headsetControl = softwareSystem "HeadsetControl" "The core software/firmware responsible for managing the headset's functions, settings, and communication." "Software/Firmware"
        headsetControlTray = softwareSystem "HeadsetControl Tray" "A tray application that allows users to manage their headset settings and view status information." "Application" {
            # Define containers within headsetControlTray
            trayAppClient = container "Tray Application Client" "Provides the user interface and interacts with other services." "Python with Qt" "GUI"
            settingsService = container "Settings Service" "Manages loading and saving of headset configurations." "Python" "Service"
            headsetComm = container "Headset Communication Service" "Handles communication with the HeadsetControl system." "Python" "Service"

            # Define relationships between these new containers and existing elements
            # Note: 'user -> headsetControlTray' is already defined at the model level.
            # We need to refine this for the container view.
            # The following relationships will be shown in the container diagram.

            # User interacts with the TrayAppClient
            user -> trayAppClient "Uses" "Interacts with the GUI"

            # TrayAppClient uses other internal services
            trayAppClient -> settingsService "Uses" "Loads/Saves settings"
            trayAppClient -> headsetComm "Uses" "Sends commands/receives status"

            # HeadsetComm interacts with the external headsetControl system
            headsetComm -> headsetControl "Controls/Manages" "Sends commands to and receives status from the headset control system."
        }

        user -> headsetControlTray "Uses" "Interacts with the tray application to view status and change settings."
        headsetControlTray -> headsetControl "Controls/Manages" "Sends commands to and receives status from the headset control system."
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
