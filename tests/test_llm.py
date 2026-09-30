"""
Tests for the LLM engine module.

Validates prompt construction, response parsing, device command extraction,
and conversation context management.
"""

import time

import pytest

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from llm_engine import LLMEngine
from prompt_manager import PromptManager


class TestPromptManager:
    """Tests for the prompt manager."""

    def setup_method(self):
        """Create a fresh prompt manager for each test."""
        self.pm = PromptManager(
            system_prompt_path="nonexistent",  # Use fallback prompt
            max_turns=3,
            context_timeout_s=5,
        )

    def test_default_system_prompt(self):
        """Should use fallback prompt if file doesn't exist."""
        assert "voice assistant" in self.pm.system_prompt.lower()

    def test_build_prompt_basic(self):
        """Build prompt should include system message and user query."""
        messages = self.pm.build_prompt("What is the weather?")

        assert len(messages) == 2  # system + user
        assert messages[0]["role"] == "system"
        assert messages[1]["role"] == "user"
        assert messages[1]["content"] == "What is the weather?"

    def test_conversation_history(self):
        """Adding turns should be reflected in the prompt."""
        self.pm.add_turn("Hello", "Hi there!")
        self.pm.add_turn("How are you?", "I'm doing well.")

        messages = self.pm.build_prompt("What can you do?")

        # system + 2 history turns (4 messages) + current query
        assert len(messages) == 6

        assert messages[1]["content"] == "Hello"
        assert messages[2]["content"] == "Hi there!"
        assert messages[3]["content"] == "How are you?"
        assert messages[4]["content"] == "I'm doing well."
        assert messages[5]["role"] == "user"
        assert messages[5]["content"] == "What can you do?"

    def test_sliding_window(self):
        """History should be trimmed to max_turns."""
        for i in range(5):
            self.pm.add_turn(f"Question {i}", f"Answer {i}")

        assert self.pm.context_length == 3

        messages = self.pm.build_prompt("Latest question")
        # system + 3 turns (6 messages) + current = 8
        assert len(messages) == 8

        # Should have the latest 3 turns
        assert messages[1]["content"] == "Question 2"

    def test_clear_context(self):
        """Clearing context should remove all history."""
        self.pm.add_turn("Test", "Response")
        assert self.pm.context_length == 1

        self.pm.clear_context()
        assert self.pm.context_length == 0

    def test_context_timeout(self):
        """Context should auto-clear after timeout."""
        self.pm = PromptManager(
            system_prompt_path="nonexistent",
            max_turns=3,
            context_timeout_s=1,  # 1 second timeout
        )

        self.pm.add_turn("Test", "Response")
        assert self.pm.context_length == 1

        # Wait for timeout
        time.sleep(1.5)

        # Building a new prompt should trigger timeout check
        messages = self.pm.build_prompt("New question")
        assert len(messages) == 2  # system + user only (history cleared)

    def test_history_summary(self):
        """Get a readable summary of conversation history."""
        self.pm.add_turn("Hello", "Hi!")
        summary = self.pm.get_history_summary()
        assert "Hello" in summary
        assert "Hi!" in summary

    def test_empty_history_summary(self):
        """Empty history should return appropriate message."""
        summary = self.pm.get_history_summary()
        assert "No conversation history" in summary


class TestLLMEngine:
    """Tests for the LLM engine (without loaded model)."""

    def setup_method(self):
        """Create an LLM engine without a real model."""
        self.engine = LLMEngine(
            model_path="nonexistent/model.gguf",
            system_prompt_path="nonexistent",
            n_threads=2,
        )

    def test_init_without_model(self):
        """Engine should initialise without crashing."""
        assert self.engine.is_available is False

    def test_query_without_model(self):
        """Query should return error message if model not loaded."""
        result = self.engine.query("Hello")
        assert "sorry" in result.lower() or "model" in result.lower()

    def test_parse_response_with_command(self):
        """Should extract device commands from response text."""
        response = (
            "Turning on the living room light. "
            "[DEVICE_CMD: action=on, device=living_room_light]"
        )

        clean_text, commands = self.engine.parse_response(response)

        assert "Turning on the living room light" in clean_text
        assert "[DEVICE_CMD" not in clean_text
        assert len(commands) == 1
        assert commands[0]["action"] == "on"
        assert commands[0]["device"] == "living_room_light"

    def test_parse_response_multiple_commands(self):
        """Should extract multiple device commands."""
        response = (
            "Sure, I'll turn on both lights. "
            "[DEVICE_CMD: action=on, device=living_room_light] "
            "[DEVICE_CMD: action=on, device=bedroom_light]"
        )

        clean_text, commands = self.engine.parse_response(response)

        assert len(commands) == 2
        assert commands[0]["device"] == "living_room_light"
        assert commands[1]["device"] == "bedroom_light"

    def test_parse_response_no_commands(self):
        """Should return empty command list for plain responses."""
        response = "The capital of France is Paris."
        clean_text, commands = self.engine.parse_response(response)

        assert clean_text == "The capital of France is Paris."
        assert len(commands) == 0

    def test_parse_response_with_value(self):
        """Should parse parameterised commands."""
        response = (
            "Setting brightness to 50%. "
            "[DEVICE_CMD: action=brightness(50), device=living_room_light]"
        )

        clean_text, commands = self.engine.parse_response(response)

        assert len(commands) == 1
        assert commands[0]["action"] == "brightness(50)"
        assert commands[0]["device"] == "living_room_light"

    def test_parse_incomplete_command(self):
        """Should reject commands missing required fields."""
        response = "[DEVICE_CMD: action=on]"  # Missing device
        clean_text, commands = self.engine.parse_response(response)
        assert len(commands) == 0

    def test_clear_context(self):
        """Should clear context without error."""
        self.engine.clear_context()
        assert self.engine.prompt_manager.context_length == 0

    def test_model_lifecycle(self):
        """Test unload and reload methods."""
        self.engine.unload_model()
        assert self.engine.is_available is False
