"""
Blueprint: /api/recommendations

Provides personalized recommendation endpoints for Create and Chat pages.
"""

from flask import Blueprint, jsonify, request

from src.logger import get_logger
from ..services.recommendation_service import get_recommendation_service

recommendations_bp = Blueprint("recommendations", __name__)


@recommendations_bp.route("/recommendations/create", methods=["GET"])
def get_create_recommendations():
    """Get recommendation chips for the Create page.

    Query params:
        count (int): Number of recommendations (default 4, max 8)

    Returns:
        200 with ``{ "recommendations": ["...", ...] }``
    """
    count = min(int(request.args.get("count", 4)), 8)
    service = get_recommendation_service()
    recs = service.get_create_recommendations(count)
    return jsonify({"recommendations": recs})


@recommendations_bp.route("/recommendations/chat", methods=["GET"])
def get_chat_recommendations():
    """Get recommendation prompts for the Chat page.

    Query params:
        count (int): Number of recommendations (default 4, max 8)

    Returns:
        200 with ``{ "recommendations": ["...", ...] }``
    """
    count = min(int(request.args.get("count", 4)), 8)
    service = get_recommendation_service()
    recs = service.get_chat_recommendations(count)
    return jsonify({"recommendations": recs})


@recommendations_bp.route("/recommendations/click", methods=["POST"])
def mark_recommendation_clicked():
    """Mark a recommendation as clicked (won't show again).

    Request JSON body::

        {
            "text": "the recommendation text",
            "context": "create" | "chat"
        }

    Returns:
        200 with ``{ "ok": true }``
    """
    body = request.get_json(force=True, silent=True) or {}
    text = body.get("text", "").strip()
    context = body.get("context", "create")

    if not text:
        return jsonify({"error": "text is required"}), 400

    service = get_recommendation_service()
    service.mark_clicked(text, context)
    return jsonify({"ok": True})
