"""
Chat service powered by Gemini for creative music advising.

Provides conversational music suggestions including lyrics, genres,
and actionable JSON blocks the frontend can parse.
"""

import json
import re
import threading
from typing import Any, Dict, List, Optional

from src.clients.gemini import GeminiClient
from src.logger import get_logger

SYSTEM_PROMPT = """\
You are a creative music advisor and songwriting assistant. Your role is to help \
users brainstorm song ideas, write lyrics, suggest genres/styles, and refine their \
musical vision.

Guidelines:
- Be enthusiastic and encouraging about the user's ideas.
- When suggesting songs, include genre tags, mood descriptions, and style notes.
- When writing lyrics, use proper song structure (verse, chorus, bridge, etc.) and \
  wrap them in a code block labeled [Lyrics].
- When you have a concrete, actionable suggestion the user might want to generate, \
  include a JSON block in your response wrapped in ```json ... ``` fences with this \
  structure:
  {
    "action": "generate",
    "mode": "custom" or "inspiration",
    "title": "Song Title",
    "tags": "genre, mood, style",
    "prompt": "Full lyrics (MUST include the complete lyrics with section markers like [Verse], [Chorus], etc.)",
    "description": "Short description for inspiration mode"
  }
  IMPORTANT: The "prompt" field MUST contain the full lyrics text. This field is used \
  to populate the lyrics editor on the creation page. Never leave it empty if you have \
  written lyrics in your response. Copy the full lyrics into this field.
  You may include multiple JSON blocks if you have several suggestions.
- Keep responses conversational and not overly long.
- If the user is vague, ask clarifying questions about mood, genre, tempo, theme, etc.
- Always respond in Chinese (unless the user uses another language).
"""


class ChatService:
    """Wraps GeminiClient to provide a music-focused chat experience."""

    def __init__(self):
        self._gemini = GeminiClient()
        self._logger = get_logger()

    def chat(
        self, message: str, history: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """Send a chat message and return the AI reply with parsed suggestions.

        Args:
            message: The user's latest message.
            history: Previous conversation turns, each with keys ``role``
                     ("user" or "assistant") and ``text``.

        Returns:
            Dict with ``reply`` (str) and ``suggestions`` (list of parsed JSON blocks).
        """
        # Build Gemini contents from history
        contents = self._build_contents(message, history or [])

        try:
            response_content = self._gemini.chat(
                messages=contents,
                system_instruction=SYSTEM_PROMPT,
            )
            reply_text = GeminiClient.extract_text(response_content)
        except Exception as exc:
            self._logger.error(f"ChatService: Gemini call failed: {exc}")
            return {
                "reply": "Sorry, I encountered an error. Please try again.",
                "suggestions": [],
            }

        # Parse JSON suggestion blocks from the reply
        suggestions = self._parse_json_blocks(reply_text)

        return {
            "reply": reply_text,
            "suggestions": suggestions,
        }

    def _build_contents(
        self, message: str, history: List[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """Convert chat history + new message into Gemini contents format."""
        contents: List[Dict[str, Any]] = []

        for turn in history:
            role = turn.get("role", "user")
            text = turn.get("text", "")
            if role == "assistant":
                contents.append({"role": "model", "parts": [{"text": text}]})
            else:
                contents.append({"role": "user", "parts": [{"text": text}]})

        # Append the current user message
        contents.append({"role": "user", "parts": [{"text": message}]})
        return contents

    @staticmethod
    def _parse_json_blocks(text: str) -> List[Dict[str, Any]]:
        """Extract JSON blocks from markdown fenced code blocks in the text."""
        suggestions: List[Dict[str, Any]] = []
        # Match ```json ... ``` blocks
        pattern = r"```json\s*\n(.*?)\n\s*```"
        matches = re.findall(pattern, text, re.DOTALL)

        for block in matches:
            try:
                parsed = json.loads(block)
                if isinstance(parsed, dict):
                    suggestions.append(parsed)
                elif isinstance(parsed, list):
                    suggestions.extend(
                        item for item in parsed if isinstance(item, dict)
                    )
            except json.JSONDecodeError:
                continue

        return suggestions


# ------------------------------------------------------------------ singleton

_service: Optional[ChatService] = None
_service_lock = threading.Lock()


def get_chat_service() -> ChatService:
    """Return the singleton ChatService instance."""
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = ChatService()
    return _service
