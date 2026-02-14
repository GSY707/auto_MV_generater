"""
Thread-safe in-memory task store with JSON persistence.

Tracks Suno generation tasks, their statuses, and associated clip data.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import get_config
from src.logger import get_logger


class TaskStore:
    """Thread-safe task store backed by an in-memory dict and JSON file."""

    def __init__(self, persist_path: Optional[Path] = None):
        self._lock = threading.Lock()
        self._logger = get_logger()
        cfg = get_config()
        self._persist_path = persist_path or (cfg.output_dir / ".task_store.json")
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._load()

    # ------------------------------------------------------------------ persistence

    def _load(self):
        """Load tasks from the JSON persistence file if it exists."""
        if self._persist_path.exists():
            try:
                with open(self._persist_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._tasks = data
                    self._logger.info(
                        f"TaskStore: loaded {len(self._tasks)} tasks from {self._persist_path}"
                    )
            except Exception as exc:
                self._logger.warning(f"TaskStore: failed to load persistence file: {exc}")

    def _save(self):
        """Persist current state to JSON (caller must hold the lock)."""
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump(self._tasks, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            self._logger.warning(f"TaskStore: failed to persist: {exc}")

    # ------------------------------------------------------------------ public API

    def add(self, task_id: str, mode: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Register a newly submitted task."""
        record = {
            "task_id": task_id,
            "status": "PENDING",
            "progress": "0%",
            "mode": mode,
            "params": params,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "clips": [],
            "saved": False,
            "saved_files": [],
        }
        with self._lock:
            self._tasks[task_id] = record
            self._save()
        self._logger.info(f"TaskStore: added task {task_id} (mode={mode})")
        return dict(record)

    def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Return a copy of a task record, or None."""
        with self._lock:
            rec = self._tasks.get(task_id)
            return dict(rec) if rec else None

    def list_all(self) -> List[Dict[str, Any]]:
        """Return copies of all task records."""
        with self._lock:
            return [dict(r) for r in self._tasks.values()]

    def get_active_task_ids(self) -> List[str]:
        """Return task IDs that are not yet in a terminal state."""
        terminal = {"SUCCESS", "FAILURE"}
        with self._lock:
            return [
                tid for tid, rec in self._tasks.items()
                if rec.get("status") not in terminal
            ]

    def update_from_suno_response(
        self, task_id: str, suno_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Parse a Suno query_task response and update the stored record.

        Expected suno_data structure::

            {
                "code": "success",
                "data": {
                    "task_id": "...",
                    "status": "SUCCESS",
                    "progress": "100%",
                    "data": [ {clip1}, {clip2} ]
                }
            }

        Clips live at suno_data["data"]["data"].
        Status is at suno_data["data"]["status"].
        """
        inner = suno_data.get("data") or {}
        if not isinstance(inner, dict):
            self._logger.warning(
                f"TaskStore: unexpected suno_data['data'] type for {task_id}"
            )
            return self.get(task_id)

        new_status = inner.get("status", "")
        new_progress = inner.get("progress", "")
        clips = inner.get("data") or []

        with self._lock:
            rec = self._tasks.get(task_id)
            if rec is None:
                self._logger.warning(f"TaskStore: unknown task_id {task_id}")
                return None

            old_status = rec.get("status")

            if new_status:
                rec["status"] = new_status
            if new_progress:
                rec["progress"] = new_progress
            if clips and isinstance(clips, list):
                rec["clips"] = clips

            # Detect completion transition
            if new_status == "SUCCESS" and old_status != "SUCCESS":
                rec["finished_at"] = datetime.now(timezone.utc).isoformat()
                self._save()
                # Trigger auto-save in a background thread
                record_copy = dict(rec)
                threading.Thread(
                    target=self._auto_save_background,
                    args=(task_id, record_copy),
                    daemon=True,
                ).start()
            else:
                self._save()

            return dict(rec)

    def delete(self, task_id: str) -> bool:
        """删除一个任务记录。返回是否成功删除。"""
        with self._lock:
            if task_id in self._tasks:
                del self._tasks[task_id]
                self._save()
                self._logger.info(f"TaskStore: deleted task {task_id}")
                return True
            return False

    def mark_saved(self, task_id: str, filenames: List[str]):
        """Mark a task as saved with the given filenames."""
        with self._lock:
            rec = self._tasks.get(task_id)
            if rec is not None:
                rec["saved"] = True
                rec["saved_files"] = filenames
                self._save()

    # ------------------------------------------------------------------ internals

    def _auto_save_background(self, task_id: str, record: Dict[str, Any]):
        """Run auto-save in a background thread."""
        try:
            from .auto_save import get_auto_saver

            saver = get_auto_saver()
            saved_files = saver.save_clips(record)
            if saved_files:
                self.mark_saved(task_id, saved_files)
                self._logger.info(
                    f"TaskStore: auto-saved {len(saved_files)} files for task {task_id}"
                )
        except Exception as exc:
            self._logger.error(f"TaskStore: auto-save failed for {task_id}: {exc}")


# ------------------------------------------------------------------ singleton

_store: Optional[TaskStore] = None
_store_lock = threading.Lock()


def get_task_store() -> TaskStore:
    """Return the singleton TaskStore instance."""
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = TaskStore()
    return _store
