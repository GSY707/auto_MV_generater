"""
Blueprint: /api/chat

AI-powered music advising chat endpoint.
"""

from flask import Blueprint, jsonify, request

from src.logger import get_logger
from ..services.chat_service import get_chat_service

chat_bp = Blueprint("chat", __name__)


@chat_bp.route("/chat", methods=["POST"])
def chat():
    """Send a message to the music advisor chatbot.

    Request JSON body::

        {
            "message": "Help me write a pop song about summer",
            "history": [
                {"role": "user", "text": "..."},
                {"role": "assistant", "text": "..."}
            ]
        }

    Returns:
        200 with ``{ "reply": "...", "suggestions": [...] }``
        400 if message is missing.
    """
    logger = get_logger()
    body = request.get_json(force=True, silent=True) or {}

    message = body.get("message", "").strip()
    if not message:
        return jsonify({"error": "message is required"}), 400

    history = body.get("history", [])

    try:
        service = get_chat_service()
        result = service.chat(message, history)
        return jsonify(result)
    except Exception as exc:
        logger.error(f"chat: error: {exc}")
        return jsonify({
            "error": f"Chat service error: {str(exc)}",
            "reply": "Sorry, I encountered an error. Please try again.",
            "suggestions": [],
        }), 500
