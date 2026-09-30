"""
LLM Query Engine module.

Processes transcribed text queries and generates responses using a quantized
on-device LLM (Phi-3.5-mini or Qwen2-1.5B) via llama.cpp.
"""

import re
import time
from pathlib import Path
from typing import List, Optional, Tuple

from loguru import logger

from prompt_manager import PromptManager

try:
    from llama_cpp import Llama
    HAS_LLAMA = True
except ImportError:
    HAS_LLAMA = False
    logger.warning(
        "llama-cpp-python not installed. LLM engine will be unavailable. "
        "Install with: pip install llama-cpp-python"
    )


class LLMEngine:
    """
    LLM query engine using llama.cpp for on-device inference.

    Supports quantized GGUF models optimised for Raspberry Pi 5.
    Maintains conversation context through the PromptManager.
    """

    def __init__(
        self,
        model_path: str = "models/llm/phi-3.5-mini-instruct.Q4_K_M.gguf",
        system_prompt_path: str = "config/system_prompt.txt",
        n_threads: int = 4,
        n_gpu_layers: int = 0,
        temperature: float = 0.3,
        max_tokens: int = 100,
        context_window: int = 2048,
        context_turns: int = 3,
        context_timeout_s: int = 120,
    ):
        """
        Initialise the LLM engine.

        Args:
            model_path: Path to the GGUF model file.
            system_prompt_path: Path to the system prompt text file.
            n_threads: Number of CPU threads for inference.
            n_gpu_layers: Number of layers to offload to GPU (0 for CPU only).
            temperature: Sampling temperature (0.0 = deterministic, 1.0 = creative).
            max_tokens: Maximum tokens to generate per response.
            context_window: Context window size in tokens.
            context_turns: Number of conversation turns to maintain.
            context_timeout_s: Seconds of inactivity before clearing context.
        """
        self.model_path = Path(model_path)
        self.n_threads = n_threads
        self.n_gpu_layers = n_gpu_layers
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.context_window = context_window
        self._model = None

        # Initialise prompt manager
        self.prompt_manager = PromptManager(
            system_prompt_path=system_prompt_path,
            max_turns=context_turns,
            context_timeout_s=context_timeout_s,
        )

        if HAS_LLAMA:
            self._load_model()

    def _load_model(self):
        """Load the LLM model into memory."""
        if not self.model_path.exists():
            logger.error(
                f"LLM model not found at {self.model_path}. "
                f"Run scripts/download_models.sh to download models."
            )
            return

        try:
            logger.info(f"Loading LLM model from {self.model_path}...")
            start_time = time.time()

            self._model = Llama(
                model_path=str(self.model_path),
                n_ctx=self.context_window,
                n_threads=self.n_threads,
                n_gpu_layers=self.n_gpu_layers,
                use_mmap=True,       # Memory-map model for lower RAM usage
                use_mlock=False,     # Don't lock in RAM (allows swapping if needed)
                verbose=False,
            )

            load_time = time.time() - start_time
            logger.info(f"LLM model loaded in {load_time:.1f}s")

        except Exception as e:
            logger.error(f"Failed to load LLM model: {e}")
            self._model = None

    def query(self, user_text: str) -> str:
        """
        Process a user query and generate a response.

        Args:
            user_text: The user's transcribed text query.

        Returns:
            The LLM's response text, including any device commands.
        """
        if self._model is None:
            logger.error("LLM model not loaded")
            return "I'm sorry, my language model isn't loaded. Please check the setup."

        try:
            start_time = time.time()

            # Build prompt with conversation context
            messages = self.prompt_manager.build_prompt(user_text)

            logger.debug(f"Querying LLM with: '{user_text}'")

            # Run chat completion
            response = self._model.create_chat_completion(
                messages=messages,
                temperature=self.temperature,
                max_tokens=self.max_tokens,
                top_p=0.9,
                repeat_penalty=1.1,
                stop=["<|end|>", "<|endoftext|>", "</s>"],
            )

            # Extract response text
            response_text = response["choices"][0]["message"]["content"].strip()

            # Update conversation history
            self.prompt_manager.add_turn(user_text, response_text)

            inference_time = time.time() - start_time
            tokens_generated = response["usage"].get("completion_tokens", 0)
            tokens_per_sec = (
                tokens_generated / inference_time if inference_time > 0 else 0
            )

            logger.info(
                f"LLM response ({inference_time:.1f}s, "
                f"{tokens_generated} tokens, {tokens_per_sec:.1f} tok/s): "
                f"'{response_text[:100]}...'"
            )

            return response_text

        except Exception as e:
            logger.error(f"LLM query error: {e}")
            return "I'm sorry, I encountered an error processing your request."

    def parse_response(self, response_text: str) -> Tuple[str, List[dict]]:
        """
        Parse the LLM response to extract device commands and clean text.

        Separates the natural language response from any [DEVICE_CMD: ...] tags.

        Args:
            response_text: The raw LLM response text.

        Returns:
            Tuple of (clean_text, list_of_device_commands).
            Each device command is a dict with 'action' and 'device' keys.
        """
        device_commands = []

        # Extract all [DEVICE_CMD: ...] tags
        pattern = r'\[DEVICE_CMD:\s*([^\]]+)\]'
        matches = re.findall(pattern, response_text)

        for match in matches:
            cmd = self._parse_device_cmd(match)
            if cmd:
                device_commands.append(cmd)

        # Remove device command tags from the text for TTS
        clean_text = re.sub(pattern, '', response_text).strip()
        # Clean up extra whitespace and newlines
        clean_text = re.sub(r'\n+', ' ', clean_text).strip()
        clean_text = re.sub(r'\s+', ' ', clean_text)

        if device_commands:
            logger.info(f"Extracted {len(device_commands)} device command(s)")
            for cmd in device_commands:
                logger.debug(f"  Device command: {cmd}")

        return clean_text, device_commands

    def _parse_device_cmd(self, cmd_string: str) -> Optional[dict]:
        """
        Parse a device command string into a structured dict.

        Args:
            cmd_string: Raw command string, e.g., 'action=on, device=living_room_light'.

        Returns:
            Dict with parsed command parameters, or None if parsing fails.
        """
        try:
            params = {}
            # Split by comma and parse key=value pairs
            for part in cmd_string.split(","):
                part = part.strip()
                if "=" in part:
                    key, value = part.split("=", 1)
                    params[key.strip()] = value.strip()

            if "action" in params and "device" in params:
                return params
            else:
                logger.warning(f"Incomplete device command: {cmd_string}")
                return None

        except Exception as e:
            logger.error(f"Failed to parse device command '{cmd_string}': {e}")
            return None

    def clear_context(self):
        """Clear the conversation history."""
        self.prompt_manager.clear_context()
        logger.info("Conversation context cleared")

    def unload_model(self):
        """Unload the model from memory to free RAM."""
        self._model = None
        logger.info("LLM model unloaded")

    def reload_model(self):
        """Reload the model into memory."""
        if HAS_LLAMA:
            self._load_model()

    @property
    def is_available(self) -> bool:
        """Check if the LLM engine is ready for queries."""
        return self._model is not None
