workspace "HeadsetControl System" "User controlling SteelSeries headset via HeadsetControl Tray" {
    model {
        user = person "User" "A person using the HeadsetControl Tray to manage their SteelSeries headset."
        headsetControlTray = softwareSystem "HeadsetControl Tray" "A desktop tray application for controlling SteelSeries headsets." {
            tags "Internal"

            desktopApplication = container "Desktop Application" "Main user-facing application providing system tray icon, settings UI, and headset control logic." "Python, PySide6 (Qt)" {
                mainApplication = component "Main Application" "Coordinates application startup, main event loop, and top-level component interactions. Handles udev rule prompts." "Python (app.py)"
                systemTrayUI = component "System Tray UI" "Manages the system tray icon, context menu, and notifications. Displays headset status and provides quick access to settings." "Python, PySide6 (ui/system_tray_icon.py)"
                headsetService = component "Headset Service" "Abstracts headset communication. Gets/sets parameters (battery, chatmix, sidetone, EQ) via direct HID or headsetcontrol CLI." "Python, python-hid, subprocess (headset_service.py)"
                configManager = component "Configuration Manager" "Loads and saves application settings (e.g., last sidetone level, active EQ) and custom EQ curves." "Python (config_manager.py)"
                settingsDialogUI = component "Settings Dialog UI" "Provides a GUI for detailed headset configuration, EQ management, and application preferences." "Python, PySide6 (ui/settings_dialog.py)"
                chatmixAudioManager = component "ChatMix Audio Manager" "Adjusts PipeWire sink input volumes based on headset chatmix value to balance game/chat audio." "Python (ui/chatmix_manager.py)"
                equalizerEditorUI = component "Equalizer Editor UI" "Specialized UI widget within the Settings Dialog for creating, editing, and selecting EQ curves." "Python, PySide6 (ui/equalizer_editor_widget.py)"
            }
            configurationStorage = container "Configuration Storage" "Stores user preferences, custom EQ curves, and last known headset settings." "JSON files on disk"
        }
        steelSeriesHeadset = softwareSystem "SteelSeries Headset" "The physical SteelSeries headset device." {
            tags "External" "PhysicalDevice"
        }
        operatingSystem = softwareSystem "Operating System" "The underlying operating system providing desktop environment, HID access, and privilege management." {
            description "Manages Desktop Environment, udev/HID for device interaction, and PolicyKit for administrative privileges."
            tags "External"
        }
        pipewireAudioServer = softwareSystem "PipeWire Audio Server" "The audio server responsible for managing audio streams and levels." {
            tags "External"
        }
        headsetcontrolCLI = softwareSystem "headsetcontrol CLI" "The command-line interface for controlling SteelSeries headsets." {
            tags "External" "CLI"
        }

        user -> headsetControlTray.desktopApplication.systemTrayUI "Interacts with"
        user -> headsetControlTray.desktopApplication.settingsDialogUI "Interacts with"

        headsetControlTray.desktopApplication.mainApplication -> headsetControlTray.desktopApplication.systemTrayUI "Creates and shows"
        headsetControlTray.desktopApplication.mainApplication -> headsetControlTray.desktopApplication.headsetService "Initializes, uses for udev check"
        headsetControlTray.desktopApplication.mainApplication -> headsetControlTray.desktopApplication.configManager "Initializes"
        headsetControlTray.desktopApplication.mainApplication -> operatingSystem "Uses for PolicyKit during udev setup"

        headsetControlTray.desktopApplication.systemTrayUI -> headsetControlTray.desktopApplication.headsetService "Uses to get status, set parameters"
        headsetControlTray.desktopApplication.systemTrayUI -> headsetControlTray.desktopApplication.configManager "Uses to get/set persisted settings"
        headsetControlTray.desktopApplication.systemTrayUI -> headsetControlTray.desktopApplication.settingsDialogUI "Opens"
        headsetControlTray.desktopApplication.systemTrayUI -> headsetControlTray.desktopApplication.chatmixAudioManager "Uses to update audio volumes"

        headsetControlTray.desktopApplication.settingsDialogUI -> headsetControlTray.desktopApplication.headsetService "Uses to get status, set parameters"
        headsetControlTray.desktopApplication.settingsDialogUI -> headsetControlTray.desktopApplication.configManager "Uses to get/set settings and EQ curves"
        headsetControlTray.desktopApplication.settingsDialogUI -> headsetControlTray.desktopApplication.equalizerEditorUI "Contains"

        headsetControlTray.desktopApplication.equalizerEditorUI -> headsetControlTray.desktopApplication.configManager "Uses to save/load EQ curves"
        headsetControlTray.desktopApplication.equalizerEditorUI -> headsetControlTray.desktopApplication.headsetService "Uses to apply EQ curves"

        headsetControlTray.desktopApplication.headsetService -> steelSeriesHeadset "Controls/Monitors via HID"
        headsetControlTray.desktopApplication.headsetService -> headsetcontrolCLI "Delegates control to / Fallback for"
        headsetControlTray.desktopApplication.headsetService -> operatingSystem "Uses udev/HID subsystem"

        headsetControlTray.desktopApplication.configManager -> configurationStorage "Reads from/Writes to"

        headsetControlTray.desktopApplication.chatmixAudioManager -> pipewireAudioServer "Manages audio levels of applications"
    }

    views {
        systemContext headsetControlTray "SystemContext" "System Context diagram for HeadsetControl Tray" {
            include *
            autoLayout
        }

        container headsetControlTray "ContainerView" "Container diagram for HeadsetControl Tray" {
            include *
            autoLayout
        }

        component headsetControlTray.desktopApplication "ComponentView" "Component diagram for Desktop Application" {
            include *
            autoLayout
        }
    }
}
