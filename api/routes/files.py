"""
Blueprint: /api/output, /api/config, /api/clips

File listing, file serving, config info, and WAV URL retrieval.
"""

import os
from pathlib import Path

from flask import Blueprint, jsonify, send_from_directory

from src.clients.suno import SunoClient
from src.config import get_config
from src.logger import get_logger

files_bp = Blueprint("files", __name__)


@files_bp.route("/output", methods=["GET"])
def list_output_files():
    """List files in the output directory.

    Excludes hidden files and the .task_store.json persistence file.

    Returns:
        200 with a list of filename strings.
    """
    cfg = get_config()
    output_dir = cfg.output_dir

    if not output_dir.exists():
        return jsonify([])

    files = []
    for entry in sorted(output_dir.iterdir()):
        name = entry.name
        # Skip hidden files and the task store persistence file
        if name.startswith(".") or name == ".task_store.json":
            continue
        if entry.is_file():
            files.append({
                "name": name,
                "size": entry.stat().st_size,
                "modified": entry.stat().st_mtime,
            })

    return jsonify(files)


@files_bp.route("/output/<path:filename>", methods=["GET"])
def serve_output_file(filename: str):
    """Serve a file from the output directory.

    Args:
        filename: The filename to serve.

    Returns:
        The file contents, or 404 if not found.
    """
    cfg = get_config()
    output_dir = str(cfg.output_dir)
    return send_from_directory(output_dir, filename)


@files_bp.route("/config", methods=["GET"])
def get_config_info():
    """Return current configuration info for the frontend.

    Returns:
        200 with config details (no secrets).
    """
    cfg = get_config()

    available_models = [
        "chirp-v4",
        "chirp-v3-5",
        "chirp-v3",
    ]

    return jsonify({
        "suno_model": cfg.suno_model,
        "gemini_model": cfg.gemini_model,
        "gemini_backend": cfg.gemini_backend,
        "available_models": available_models,
    })


@files_bp.route("/clips/<clip_id>/wav", methods=["GET"])
def get_clip_wav(clip_id: str):
    """Get the WAV download URL for a clip.

    Args:
        clip_id: The Suno clip ID.

    Returns:
        200 with the WAV URL data from Suno.
        502 if the Suno call fails.
    """
    logger = get_logger()
    suno = SunoClient()

    try:
        result = suno.get_wav_url(clip_id)
        return jsonify(result)
    except Exception as exc:
        logger.error(f"clips/{clip_id}/wav: Suno call failed: {exc}")
        return jsonify({"error": f"Failed to get WAV URL: {str(exc)}"}), 502
