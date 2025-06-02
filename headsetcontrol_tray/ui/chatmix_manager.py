# chatmix_manager.py
import subprocess
import json
import logging
from typing import List, Dict, Optional, Tuple, Any

# Assuming app_config is in the parent directory relative to this file if it's in a 'ui' subfolder
# Adjust the import path if necessary, e.g., from .. import app_config
# from .. import app_config
# For now, let's assume app_config can be imported directly or we'll pass necessary config.
# We'll primarily need chat_app_identifiers from config_manager.

logger = logging.getLogger(__name__) # Will be configured by your main app's logging setup


class ChatMixManager:
    def __init__(self, config_manager): # cfg_mgr.ConfigManager
        self.config_manager = config_manager
        # Load chat app identifiers (list of strings for application.name or application.process.binary)
        # Ensure these are lowercase for case-insensitive matching later.
        self.chat_app_identifiers_config = [
            ident.lower() for ident in
            self.config_manager.get_setting("chat_app_identifiers", ["Discord", "WEBRTC VoiceEngine"])
        ]
        # Reference volume for 100% (PipeWire uses floats, typically 0.0 to 1.0 for normal range)
        self.reference_volume = 1.0
        logger.info(f"ChatMixManager initialized. Chat app identifiers: {self.chat_app_identifiers_config}")

    def _run_pipewire_command(self, command_args: List[str]) -> Optional[str]:
        """Runs a PipeWire command (like pw-dump or pw-cli) and returns its stdout."""
        try:
            logger.debug(f"Executing PipeWire command: {' '.join(command_args)}")
            result = subprocess.run(command_args, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            logger.error(f"Command '{' '.join(command_args)}' failed with error: {e.stderr.strip()}")
        except FileNotFoundError:
            logger.error(f"Command '{command_args[0]}' not found. Is PipeWire installed and in PATH?")
        except Exception as e:
            logger.error(f"An unexpected error occurred while running '{' '.join(command_args)}': {e}")
        return None

    def _get_audio_streams(self) -> List[Dict[str, Any]]:
        """
        Gets all active audio output stream nodes from PipeWire using pw-dump.
        Extracts ID, identifying properties, and current channel/volume info.
        """
        json_output = self._run_pipewire_command(['pw-dump'])
        if not json_output:
            logger.warning("Failed to get output from pw-dump.")
            return []

        try:
            all_objects = json.loads(json_output)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON from pw-dump: {e}")
            return []

        streams = []
        for obj in all_objects:
            obj_type = obj.get("type")
            if obj_type != "PipeWire:Interface:Node": # We are interested in Nodes
                continue

            info = obj.get("info", {})
            props = info.get("props", {})
            media_class = props.get("media.class")

            if media_class == "Stream/Output/Audio":
                stream_id = obj.get("id")
                if stream_id is None:
                    logger.warning(f"Found Stream/Output/Audio node without an ID: {props.get('node.name', 'N/A')}")
                    continue

                # Get current channelVolumes and count from the "Props" parameter
                # The 'params' in pw-dump output for a node is an object,
                # where keys are param names (e.g., "Props", "EnumFormat").
                # Each key maps to an array of actual parameter instances.
                node_params = info.get("params", {})
                current_channel_volumes = [self.reference_volume] # Default to mono 100%
                num_channels = 1

                if "Props" in node_params and node_params["Props"]: # "Props" exists and is not empty list
                    # "Props" parameter is usually an array with one object in it
                    props_param_instance = node_params["Props"][0] if isinstance(node_params["Props"], list) and node_params["Props"] else {}
                    if "channelVolumes" in props_param_instance:
                        current_channel_volumes = props_param_instance["channelVolumes"]
                        num_channels = len(current_channel_volumes)
                    elif "volume" in props_param_instance and num_channels == 1: # Fallback for mono if only 'volume' is present
                        current_channel_volumes = [props_param_instance["volume"]]

                streams.append({
                    "id": stream_id,
                    "props": props, # application.name, application.process.binary, etc.
                    "num_channels": num_channels,
                    "current_channel_volumes": current_channel_volumes # For reference or if needed
                })
        logger.debug(f"Found {len(streams)} Stream/Output/Audio nodes.")
        return streams

    def _calculate_volumes(self, chatmix_value: int) -> Tuple[float, float]:
        """
        Calculates game and chat volumes based on ChatMix (0-128).
        0   = Full Chat (Game low, Chat full)
        64  = Balanced (Both full)
        128 = Full Game (Chat low, Game full)
        """
        chatmix_norm = chatmix_value / 128.0  # Normalize to 0.0 - 1.0

        # This creates a curve where at 0.5 (balanced), both are full.
        # As it moves away from 0.5, one channel is attenuated.
        if chatmix_norm <= 0.5:  # More towards Chat (0.0 to 0.5)
            chat_vol = self.reference_volume
            # Game volume goes from reference_volume (at chatmix 0.5) down to 0 (at chatmix 0.0)
            # Scale the 0.0-0.5 range to 0.0-1.0 for the factor
            game_vol_factor = chatmix_norm * 2.0
            game_vol = self.reference_volume * game_vol_factor
        else:  # More towards Game (0.5 to 1.0)
            game_vol = self.reference_volume
            # Chat volume goes from reference_volume (at chatmix 0.5) down to 0 (at chatmix 1.0)
            # Scale the 0.5-1.0 range to 1.0-0.0 for the factor
            chat_vol_factor = (1.0 - chatmix_norm) * 2.0
            chat_vol = self.reference_volume * chat_vol_factor

        # Clamp volumes (e.g., to prevent > 1.0 if reference_volume is 1.0)
        # And ensure a minimum if desired (e.g., 0.05 to never fully mute)
        min_audible_volume = 0.0 # Can be set to a small value like 0.05
        chat_vol = max(min_audible_volume, min(self.reference_volume, chat_vol))
        game_vol = max(min_audible_volume, min(self.reference_volume, game_vol))

        logger.debug(f"ChatMix Raw: {chatmix_value}, Norm: {chatmix_norm:.2f} -> ChatTargetVol: {chat_vol:.2f}, GameTargetVol: {game_vol:.2f}")
        return chat_vol, game_vol

    def _set_stream_volume(self, stream_id: int, target_volume: float, num_channels: int) -> bool:
        """Sets the volume for a specific stream node using its "Props" parameter."""
        if not (0.0 <= target_volume <= self.reference_volume + 0.5): # Allow slight boost
            logger.warning(f"Target volume {target_volume:.2f} for stream {stream_id} is out of expected range. Clamping.")
            target_volume = max(0.0, min(self.reference_volume, target_volume))

        # Construct the JSON payload for channelVolumes
        # Create a list of the target_volume repeated for each channel
        channel_volumes_payload = [float(f"{target_volume:.6f}") for _ in range(num_channels)] # Format to few decimal places
        
        # The JSON payload to set for the "Props" parameter
        # We are only modifying 'channelVolumes'. Other properties within "Props" remain untouched by this command.
        # PipeWire's set-param for complex objects often merges, but for safety,
        # it's better if we knew the full existing Props structure if we wanted to preserve everything else.
        # However, just setting channelVolumes is usually supported for sink-inputs.
        json_payload_str = json.dumps({"channelVolumes": channel_volumes_payload})

        logger.verbose(f"Setting volume for stream ID {stream_id} ({num_channels} channels) to {target_volume:.2f} with payload: {json_payload_str}")
        
        # Command: pw-cli set-param <object-id> <param-name> <param-json>
        success_str = self._run_pipewire_command(['pw-cli', 'set-param', str(stream_id), 'Props', json_payload_str])
        
        if success_str is not None: # Command executed, check output if needed (usually empty on success for set-param)
            logger.debug(f"pw-cli set-param for stream {stream_id} successful.")
            return True
        else:
            logger.error(f"Failed to set volume for stream ID {stream_id}.")
            return False

    def update_volumes(self, chatmix_value: Optional[int]):
        if chatmix_value is None:
            logger.debug("ChatMix value is None, skipping volume update.")
            return

        # Reload config in case it changed via settings dialog
        self.chat_app_identifiers_config = [
            ident.lower() for ident in
            self.config_manager.get_setting("chat_app_identifiers", ["Discord", "WEBRTC VoiceEngine"])
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
            # node_name = props.get("node.name", "").lower() # Can also be used

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

            logger.debug(f"Processing stream: ID={stream_id}, AppName='{props.get('application.name', '')}', "
                         f"Binary='{props.get('application.process.binary', '')}', Type={stream_type}, TargetVol={current_target_volume:.2f}")
            self._set_stream_volume(stream_id, current_target_volume, num_channels)