"""Manages PipeWire stream volumes for ChatMix functionality."""

# chatmix_manager.py
import json
import logging
import subprocess
from typing import Any

from headsetcontrol_tray.config_manager import ConfigManager

# Assuming app_config is in the parent directory relative to this file
# if it's in a 'ui' subfolder
# Adjust the import path if necessary, e.g., from .. import app_config

# For now, let's assume app_config can be imported directly or we'll pass
# necessary config. We'll primarily need chat_app_identifiers from config_manager.

logger = logging.getLogger(
    __name__,
)  # Will be configured by your main app's logging setup

CHATMIX_NORMALIZED_MIDPOINT = 0.5
FLOAT_COMPARISON_TOLERANCE = 0.001


class ChatMixManager:
    """Handles automatic volume adjustment of applications based on ChatMix values."""

    def __init__(self, config_manager: ConfigManager) -> None:  # cfg_mgr.ConfigManager
        """
        Initializes the ChatMixManager.

        Args:
            config_manager: The application's ConfigManager instance.
        """
        self.config_manager = config_manager
        # Load chat app identifiers (list of strings for application.name
        # or application.process.binary)
        # Ensure these are lowercase for case-insensitive matching later.
        self.chat_app_identifiers_config = [
            ident.lower()
            for ident in self.config_manager.get_setting(
                "chat_app_identifiers",
                ["Discord", "WEBRTC VoiceEngine"],
            )
        ]
        # Reference volume for 100% (PipeWire uses floats, typically 0.0 to 1.0
        # for normal range)
        self.reference_volume = 1.0
        self._last_set_stream_volumes: dict[str, list[float]] = {}
        # New attribute
        logger.info(
            "ChatMixManager initialized. Chat app identifiers: %s",
            self.chat_app_identifiers_config,
        )

    def _run_pipewire_command(self, command_args: list[str]) -> str | None:
        """Runs a PipeWire command (like pw-dump or pw-cli) and returns its stdout."""
        try:
            logger.debug("Executing PipeWire command: %s", " ".join(command_args))
            result = subprocess.run(  # nosec B603
                command_args,
                capture_output=True,
                text=True,
                check=True,
            )  # nosemgrep S603 # command_args are typically static like ["pw-dump"]
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            logger.exception("Command '%s' failed", " ".join(command_args))
        except FileNotFoundError:
            logger.exception(
                "Command '%s' not found. Is PipeWire installed and in PATH?",
                command_args[0] if command_args else "N/A",
            )
        # Catching any other unexpected error during pipewire command execution
        except Exception:
            logger.exception(
                "An unexpected error occurred while running '%s'",
                " ".join(command_args),
            )
        return None

    def _get_audio_streams(self) -> list[dict[str, Any]]:
        """Gets all active audio output stream nodes from PipeWire using pw-dump.

        Extracts ID, identifying properties, and current channel/volume info.
        """
        json_output = self._run_pipewire_command(["pw-dump"])
        if not json_output:
            logger.warning("Failed to get output from pw-dump.")
            return []

        try:
            all_objects = json.loads(json_output)
        except json.JSONDecodeError:
            logger.exception("Failed to parse JSON from pw-dump")
            return []

        streams = []
        for obj in all_objects:
            obj_type = obj.get("type")
            if obj_type != "PipeWire:Interface:Node":  # We are interested in Nodes
                continue

            info = obj.get("info", {})
            props = info.get("props", {})
            media_class = props.get("media.class")

            if media_class == "Stream/Output/Audio":
                stream_id = obj.get("id")
                if stream_id is None:
                    logger.warning(
                        "Found Stream/Output/Audio node without an ID: %s",  # Wrapped
                        props.get("node.name", "N/A"),
                    )
                    continue

                # Get current channelVolumes and count from the "Props" parameter
                # The 'params' in pw-dump output for a node is an object,
                # where keys are param names (e.g., "Props", "EnumFormat").
                # Each key maps to an array of actual parameter instances.
                node_params = info.get("params", {})
                current_channel_volumes = [
                    self.reference_volume,
                ]  # Default to mono 100%
                num_channels = 1

                if node_params.get("Props"):
                    # "Props" exists and is not empty list
                    # "Props" parameter is usually an array with one object in it
                    props_param_instance = (
                        node_params["Props"][0]
                        if isinstance(node_params["Props"], list) and node_params["Props"]
                        else {}
                    )
                    if "channelVolumes" in props_param_instance:
                        current_channel_volumes = props_param_instance["channelVolumes"]
                        num_channels = len(current_channel_volumes)
                    elif (
                        "volume" in props_param_instance and num_channels == 1
                    ):  # Fallback for mono if only 'volume' is present
                        current_channel_volumes = [props_param_instance["volume"]]

                streams.append(
                    {
                        "id": stream_id,
                        "props": props,
                        # application.name, application.process.binary, etc.
                        "num_channels": num_channels,
                        # For reference or if needed
                        "current_channel_volumes": current_channel_volumes,
                    },
                )
        logger.debug("Found %s Stream/Output/Audio nodes.", len(streams))  # Wrapped
        return streams

    def _calculate_volumes(self, chatmix_value: int) -> tuple[float, float]:
        """Calculates game and chat volumes based on ChatMix (0-128).

        0   = Full Chat (Game low, Chat full)
        64  = Balanced (Both full)
        128 = Full Game (Chat low, Game full)
        """
        chatmix_norm = chatmix_value / 128.0  # Normalize to 0.0 - 1.0

        # This curve ensures at CHATMIX_NORMALIZED_MIDPOINT (balanced), both are full.
        # As it moves away, one channel is attenuated.
        if chatmix_norm <= CHATMIX_NORMALIZED_MIDPOINT:  # More towards Chat (0.0 to 0.5)
            chat_vol = self.reference_volume
            # Game vol goes from reference_volume (at 0.5) down to 0 (at 0.0).
            # Scale the 0.0-0.5 range to 0.0-1.0 for factor.
            game_vol_factor = chatmix_norm * 2.0  # chatmix_norm / CHATMIX_NORMALIZED_MIDPOINT
            game_vol = self.reference_volume * game_vol_factor
        else:  # More towards Game (0.5 to 1.0)
            game_vol = self.reference_volume
            # Chat volume goes from reference_volume (at chatmix 0.5) down to 0
            # (at chatmix 1.0). Scale the 0.5-1.0 range to 1.0-0.0 for the factor.
            chat_vol_factor = (1.0 - chatmix_norm) * 2.0  # (1.0 - chatmix_norm) / (1.0 - CHATMIX_NORMALIZED_MIDPOINT)
            chat_vol = self.reference_volume * chat_vol_factor

        # Clamp volumes (e.g., to prevent > 1.0 if reference_volume is 1.0)
        # And ensure a minimum if desired (e.g., 0.05 to never fully mute).
        min_audible_volume = 0.0  # Can be set to a small value like 0.05
        chat_vol = max(min_audible_volume, min(self.reference_volume, chat_vol))
        game_vol = max(min_audible_volume, min(self.reference_volume, game_vol))

        logger.debug(
            "ChatMix Raw: %s, Norm: %.2f -> ChatTargetVol: %.2f, GameTargetVol: %.2f",
            chatmix_value,
            chatmix_norm,
            chat_vol,
            game_vol,
        )
        return chat_vol, game_vol

    def _set_stream_volume(
        self,
        stream_id: str,
        num_channels: int,
        target_volume: float,
    ) -> None:
        # Ensure target_volume is clamped between 0.0 and 1.0
        target_volume = max(0.0, min(1.0, target_volume))

        # Create a list of target volumes for each channel
        target_volumes_list = [target_volume] * num_channels

        # Check if volume needs to be changed
        last_volumes = self._last_set_stream_volumes.get(stream_id)
        if (
            last_volumes is not None
            and len(last_volumes) == num_channels
            and all(abs(last_vol - target_volume) < FLOAT_COMPARISON_TOLERANCE for last_vol in last_volumes)
        ):  # Compare with a tolerance
            logger.debug(
                "Volume for stream ID %s already at target %.2f. Skipping pw-cli.",
                stream_id,
                target_volume,
            )
            return

        payload_dict = {"channelVolumes": target_volumes_list}
        payload_json = json.dumps(payload_dict)  # Ensure json is imported

        logger.debug(
            "Setting volume for stream ID %s (%s channels) to %.2f with payload: %s",
            stream_id,
            num_channels,
            target_volume,
            payload_json,
        )

        # Construct the command
        cmd = ["pw-cli", "set-param", str(stream_id), "Props", payload_json]
        logger.debug("Executing PipeWire command: %s", " ".join(cmd))

        try:
            process = subprocess.run(  # nosec B603
                cmd,
                capture_output=True,
                text=True,
                check=True,
            )  # nosemgrep S603 # cmd uses pw-cli with stream_id from pw-dump and controlled JSON.
            logger.debug(
                "pw-cli set-param for stream %s successful. Output: %s",
                stream_id,
                process.stdout.strip(),
            )
            self._last_set_stream_volumes[stream_id] = target_volumes_list  # Update last set volumes
        except FileNotFoundError:
            logger.exception("pw-cli command not found.")
        except subprocess.CalledProcessError as e:
            logger.exception(
                "Error setting volume for stream %s using pw-cli (exit code %s)",
                stream_id,
                e.returncode,
            )
        # Catching any other unexpected error during volume setting
        except Exception:
            logger.exception(
                "An unexpected error occurred while setting volume for stream %s",
                stream_id,
            )

    def update_volumes(self, chatmix_value: int | None) -> None:
        """Updates system audio stream volumes based on the headset's chatmix value."""
        if chatmix_value is None:
            logger.debug("ChatMix value is None, skipping volume update.")
            return

        # Reload config in case it changed via settings dialog
        self.chat_app_identifiers_config = [
            ident.lower()
            for ident in self.config_manager.get_setting(
                "chat_app_identifiers",
                ["Discord", "WEBRTC VoiceEngine"],
            )
        ]

        chat_target_vol, game_target_vol = self._calculate_volumes(chatmix_value)
        active_streams = self._get_audio_streams()

        if not active_streams:
            logger.debug("No active audio streams found to update.")
            return

        for stream in active_streams:
            stream_id = stream["id"]
            props = stream["props"]
            num_channels = stream["num_channels"]

            app_name = props.get("application.name", "").lower()
            app_binary = props.get("application.process.binary", "").lower()

            is_chat_app = False
            for ident in self.chat_app_identifiers_config:
                if ident in app_name or ident in app_binary:
                    is_chat_app = True
                    break

            current_target_volume = game_target_vol
            stream_type = "OTHER/GAME"
            if is_chat_app:
                current_target_volume = chat_target_vol
                stream_type = "CHAT"

            logger.debug(
                ("Processing stream: ID=%s, AppName='%s', Binary='%s', Type=%s, TargetVol=%.2f"),
                stream_id,
                props.get("application.name", ""),
                props.get("application.process.binary", ""),
                stream_type,
                current_target_volume,
            )
            self._set_stream_volume(stream_id, num_channels, current_target_volume)
