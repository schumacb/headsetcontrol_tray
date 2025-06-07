workspace "HeadsetControl Architecture" "Describes the architecture of the HeadsetControl system and its related components." {

    model {
        user = person "User" "A person using the HeadsetControl Tray application to manage their headset settings." ""
        headsetControlTray = softwareSystem "HeadsetControl Tray" "A tray application that allows users to manage their headset settings and view status information." "Application"
        headsetControl = softwareSystem "HeadsetControl" "The core software/firmware responsible for managing the headset's functions, settings, and communication." "Software/Firmware"

        user -> headsetControlTray "Uses" "Interacts with the tray application to view status and change settings."
        headsetControlTray -> headsetControl "Controls/Manages" "Sends commands to and receives status from the headset control system."
    }

    views {
        systemContext headsetControlTray "SystemContext" "The system context view for the HeadsetControl Tray application." {
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
                inherits "Software System"
                icon "https://static.structurizr.com/icons/desktop-24.png"
            }
            element "Software/Firmware" {
                inherits "Software System"
                icon "https://static.structurizr.com/icons/component-24.png"
            }
            element "User" {
                inherits "Person"
            }
        }
    }

}
