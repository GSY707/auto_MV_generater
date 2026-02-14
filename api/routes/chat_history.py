"""
Blueprint: /api/chat/history

Persists AI assistant chat history across page navigation.
"""

from flask import Blueprint, jsonify, request

from src.logger import get_logger

chat_history_bp = Blueprint("chat_history", __name__)

# In-memory chat history storage (single-user app)
_chat_history = []


@chat_history_bp.route("/chat/history", methods=["GET"])
def get_chat_history():
    """Get the persisted chat history.

    Returns:
        200 with ``{ "messages": [...] }``
    """
    return jsonify({"messages": _chat_history})


@chat_history_bp.route("/chat/history", methods=["POST"])
def save_chat_history():
    """Save/replace the chat history.

    Request JSON body::

        {
            "messages": [
                {"role": "user", "text": "..."},
                {"role": "assistant", "text": "...", "suggestions": [...]}
            ]
        }

    Returns:
        200 with ``{ "ok": true }``
    """
    global _chat_history
    body = request.get_json(force=True, silent=True) or {}
    messages = body.get("messages", [])
    _chat_history = messages
    return jsonify({"ok": True})


@chat_history_bp.route("/chat/history", methods=["DELETE"])
def clear_chat_history():
    """Clear the chat history.

    Returns:
        200 with ``{ "ok": true }``
    """
    global _chat_history
    _chat_history = []
    return jsonify({"ok": True})
