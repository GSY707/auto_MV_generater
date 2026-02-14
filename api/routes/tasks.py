"""
Blueprint: /api/tasks

Query and refresh Suno generation tasks.
"""

from flask import Blueprint, jsonify, request

from src.clients.suno import SunoClient
from src.logger import get_logger
from ..services.task_store import get_task_store

tasks_bp = Blueprint("tasks", __name__)


@tasks_bp.route("/tasks", methods=["GET"])
def list_tasks():
    """List all tracked tasks, sorted by created_at descending."""
    store = get_task_store()
    tasks = store.list_all()
    tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    return jsonify(tasks)


@tasks_bp.route("/tasks/<task_id>", methods=["GET"])
def get_task(task_id: str):
    """Get a single task, querying Suno for a fresh status update.

    Returns:
        200 with the updated task record.
        404 if the task_id is not tracked.
        502 if the Suno query fails.
    """
    logger = get_logger()
    store = get_task_store()
    suno = SunoClient()

    # Ensure we know about this task
    existing = store.get(task_id)
    if existing is None:
        return jsonify({"error": f"Unknown task: {task_id}"}), 404

    try:
        suno_data = suno.query_task(task_id)
    except Exception as exc:
        logger.error(f"tasks/{task_id}: Suno query failed: {exc}")
        return jsonify({"error": f"Suno query error: {str(exc)}"}), 502

    updated = store.update_from_suno_response(task_id, suno_data)
    return jsonify(updated)


@tasks_bp.route("/tasks/<task_id>", methods=["DELETE"])
def delete_task(task_id: str):
    """删除一个任务记录。"""
    store = get_task_store()
    if store.delete(task_id):
        return jsonify({"ok": True})
    return jsonify({"error": "Task not found"}), 404


@tasks_bp.route("/tasks/refresh", methods=["POST"])
def refresh_tasks():
    """Refresh one or more tasks by querying Suno for fresh status.

    Request JSON body (optional)::

        { "task_ids": ["id1", "id2", ...] }

    If task_ids is omitted, all active (non-terminal) tasks are refreshed.

    Returns:
        200 with a list of updated task records.
    """
    logger = get_logger()
    store = get_task_store()
    suno = SunoClient()

    body = request.get_json(force=True, silent=True) or {}
    task_ids = body.get("task_ids") or store.get_active_task_ids()

    updated_records = []
    for tid in task_ids:
        try:
            suno_data = suno.query_task(tid)
            record = store.update_from_suno_response(tid, suno_data)
            if record:
                updated_records.append(record)
        except Exception as exc:
            logger.error(f"tasks/refresh: failed to refresh {tid}: {exc}")
            # Include the existing record even if refresh failed
            existing = store.get(tid)
            if existing:
                existing["_refresh_error"] = str(exc)
                updated_records.append(existing)

    updated_records.sort(key=lambda t: t.get("created_at", ""), reverse=True)
    return jsonify(updated_records)
