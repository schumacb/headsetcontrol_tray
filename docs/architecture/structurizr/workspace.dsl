workspace "HeadsetControl Architecture" "Describes the architecture of the HeadsetControl system and its related components." {

    model {
        user = person "User" "A person using the HeadsetControl Tray application to manage their headset settings." ""
        headsetControl = softwareSystem "HeadsetControl" "The core software/firmware responsible for managing the headset's functions, settings, and communication." "Software/Firmware"
        headsetControlTray = softwareSystem "HeadsetControl Tray" "A tray application that allows users to manage their headset settings and view status information." "Application" {
            hcTrayProcess = container "HeadsetControl Tray Process" "The main application process for the headset control tray." "Python" "Monolith"

            # Relationships for this single container
            user -> hcTrayProcess "Uses" "Interacts with the tray application"
            hcTrayProcess -> headsetControl "Controls/Manages" "Sends commands to and receives status from the headset control system"
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
