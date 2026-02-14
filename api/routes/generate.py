"""
Blueprint: /api/generate

Handles music generation requests by submitting tasks to the Suno API.
"""

from flask import Blueprint, jsonify, request

from src.clients.suno import SunoClient
from src.logger import get_logger
from ..services.task_store import get_task_store

generate_bp = Blueprint("generate", __name__)


@generate_bp.route("/generate", methods=["POST"])
def generate():
    """Submit a new music generation task.

    Request JSON body::

        {
            "mode": "inspiration" | "custom",
            "description": "...",      # for inspiration mode
            "prompt": "...",           # for custom mode (lyrics)
            "title": "...",            # for custom mode
            "tags": "...",             # for custom mode
            "negative_tags": "...",    # for custom mode
            "make_instrumental": false,
            "model": "chirp-v4"       # optional override
        }

    Returns:
        201 with the new task record on success.
        400 on validation errors.
        502 if the Suno API call fails.
    """
    logger = get_logger()
    body = request.get_json(force=True, silent=True) or {}

    mode = body.get("mode", "inspiration")
    make_instrumental = bool(body.get("make_instrumental", False))
    model = body.get("model") or None

    suno = SunoClient()
    store = get_task_store()

    try:
        if mode == "custom":
            prompt = body.get("prompt", "")
            title = body.get("title", "")
            tags = body.get("tags", "")
            negative_tags = body.get("negative_tags", "")

            if not prompt and not title:
                return jsonify({"error": "Custom mode requires at least a prompt or title"}), 400

            result = suno.generate_music_custom(
                prompt=prompt,
                title=title,
                tags=tags,
                mv=model,
                negative_tags=negative_tags,
                make_instrumental=make_instrumental,
            )
        else:
            # inspiration mode
            description = body.get("description", "")
            if not description:
                return jsonify({"error": "Inspiration mode requires a description"}), 400

            result = suno.generate_music_inspiration(
                description=description,
                make_instrumental=make_instrumental,
                mv=model,
            )
    except Exception as exc:
        logger.error(f"generate: Suno API call failed: {exc}")
        return jsonify({"error": f"Suno API error: {str(exc)}"}), 502

    # Check result
    if result.get("code") != "success":
        msg = result.get("message", "Unknown error")
        logger.warning(f"generate: Suno returned non-success: {result}")
        return jsonify({"error": f"Suno error: {msg}", "detail": result}), 502

    task_id = result.get("data")
    if not task_id or not isinstance(task_id, str):
        logger.warning(f"generate: unexpected task_id in response: {result}")
        return jsonify({"error": "Unexpected response from Suno", "detail": result}), 502

    # Register in task store
    original_params = {
        k: v for k, v in body.items()
        if k in ("mode", "description", "prompt", "title", "tags",
                 "negative_tags", "make_instrumental", "model")
    }
    record = store.add(task_id, mode, original_params)

    return jsonify(record), 201
