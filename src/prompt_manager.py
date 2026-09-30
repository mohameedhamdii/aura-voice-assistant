"""
Prompt Manager module.

Manages the system prompt, conversation context, and prompt formatting
for the LLM engine. Maintains a sliding window of recent exchanges.
"""

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

from loguru import logger


@dataclass
class ConversationTurn:
    """Represents a single conversation turn (user + assistant)."""
    user_message: str
    assistant_response: str
    timestamp: float = field(default_factory=time.time)


class PromptManager:
    """
    Manages conversation context and prompt construction for the LLM.

    Maintains a sliding window of recent conversation turns and handles
    context expiry after a period of inactivity.
    """

    def __init__(
        self,
        system_prompt_path: str = "config/system_prompt.txt",
        max_turns: int = 3,
        context_timeout_s: int = 120,
    ):
        """
        Initialise the prompt manager.

        Args:
            system_prompt_path: Path to the system prompt text file.
            max_turns: Maximum number of conversation turns to keep in context.
            context_timeout_s: Seconds of inactivity before clearing context.
        """
        self.max_turns = max_turns
        self.context_timeout_s = context_timeout_s
        self._system_prompt = ""
        self._conversation_history: List[ConversationTurn] = []
        self._last_interaction_time = 0.0

        # Load system prompt
        self._load_system_prompt(system_prompt_path)

    def _load_system_prompt(self, path: str):
        """Load the system prompt from a text file."""
        prompt_path = Path(path)
        if prompt_path.exists():
            self._system_prompt = prompt_path.read_text(encoding="utf-8").strip()
            logger.info(f"System prompt loaded from {path}")
        else:
            # Fallback system prompt
            self._system_prompt = (
                "You are a helpful, concise voice assistant running on a local device "
                "with no internet access. Answer questions briefly (1-3 sentences)."
            )
            logger.warning(
                f"System prompt file not found at {path}, using default prompt"
            )

    @property
    def system_prompt(self) -> str:
        """Get the current system prompt."""
        return self._system_prompt

    def update_system_prompt(self, new_prompt: str):
        """
        Update the system prompt dynamically.

        Args:
            new_prompt: New system prompt text.
        """
        self._system_prompt = new_prompt
        logger.info("System prompt updated")

    def build_prompt(self, user_query: str) -> List[dict]:
        """
        Build the complete prompt with system message, context, and user query.

        Constructs a chat-style message list compatible with llama-cpp-python's
        chat completion API.

        Args:
            user_query: The user's current query text.

        Returns:
            List of message dicts with 'role' and 'content' keys.
        """
        # Check for context timeout
        self._check_context_timeout()

        messages = []

        # System message
        messages.append({
            "role": "system",
            "content": self._system_prompt,
        })

        # Add conversation history
        for turn in self._conversation_history:
            messages.append({
                "role": "user",
                "content": turn.user_message,
            })
            messages.append({
                "role": "assistant",
                "content": turn.assistant_response,
            })

        # Add current query
        messages.append({
            "role": "user",
            "content": user_query,
        })

        logger.debug(
            f"Built prompt with {len(self._conversation_history)} history turns "
            f"and current query: '{user_query[:50]}...'"
        )

        return messages

    def add_turn(self, user_message: str, assistant_response: str):
        """
        Add a completed conversation turn to the history.

        Args:
            user_message: The user's message.
            assistant_response: The assistant's response.
        """
        turn = ConversationTurn(
            user_message=user_message,
            assistant_response=assistant_response,
        )

        self._conversation_history.append(turn)
        self._last_interaction_time = time.time()

        # Trim to sliding window size
        if len(self._conversation_history) > self.max_turns:
            removed = len(self._conversation_history) - self.max_turns
            self._conversation_history = self._conversation_history[-self.max_turns:]
            logger.debug(f"Trimmed {removed} old turns from conversation history")

    def _check_context_timeout(self):
        """Clear conversation history if the context has timed out."""
        if (
            self._last_interaction_time > 0
            and time.time() - self._last_interaction_time > self.context_timeout_s
        ):
            old_count = len(self._conversation_history)
            self.clear_context()
            if old_count > 0:
                logger.info(
                    f"Context cleared after {self.context_timeout_s}s of inactivity "
                    f"({old_count} turns removed)"
                )

    def clear_context(self):
        """Clear the conversation history."""
        self._conversation_history.clear()
        self._last_interaction_time = 0.0

    @property
    def context_length(self) -> int:
        """Get the number of turns in the conversation history."""
        return len(self._conversation_history)

    def get_history_summary(self) -> str:
        """
        Get a human-readable summary of the conversation history.

        Returns:
            Summary string of recent conversation turns.
        """
        if not self._conversation_history:
            return "No conversation history."

        lines = []
        for i, turn in enumerate(self._conversation_history):
            lines.append(f"Turn {i + 1}:")
            lines.append(f"  User: {turn.user_message[:80]}")
            lines.append(f"  Assistant: {turn.assistant_response[:80]}")
        return "\n".join(lines)
