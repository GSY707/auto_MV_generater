"""
MV 任务状态管理

独立于音乐任务的 MV 生成任务存储，支持 JSON 持久化。
"""

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.config import get_config
from src.logger import get_logger


# MV 状态常量
MV_STATUS_PENDING = "PENDING"
MV_STATUS_STORYBOARD = "GENERATING_STORYBOARD"
MV_STATUS_IMAGES = "GENERATING_IMAGES"
MV_STATUS_VIDEO = "GENERATING_VIDEO"
MV_STATUS_STITCHING = "STITCHING"
MV_STATUS_SUCCESS = "SUCCESS"
MV_STATUS_FAILURE = "FAILURE"
MV_STATUS_INTERRUPTED = "INTERRUPTED"

MV_TERMINAL = {MV_STATUS_SUCCESS, MV_STATUS_FAILURE}

# 可恢复的状态集合
MV_RECOVERABLE = {
    MV_STATUS_PENDING,
    MV_STATUS_STORYBOARD,
    MV_STATUS_IMAGES,
    MV_STATUS_VIDEO,
    MV_STATUS_STITCHING,
    MV_STATUS_INTERRUPTED,
}


class MVStore:
    """MV 任务存储"""

    def __init__(self, persist_path: Optional[Path] = None):
        self._lock = threading.Lock()
        self._logger = get_logger()
        cfg = get_config()
        self._persist_path = persist_path or (cfg.output_dir / ".mv_store.json")
        self._mv_dir = cfg.output_dir / "mv"
        self._mv_dir.mkdir(parents=True, exist_ok=True)
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        if self._persist_path.exists():
            try:
                with open(self._persist_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    self._tasks = data
                    self._logger.info(f"MVStore: loaded {len(self._tasks)} MV tasks")
            except Exception as exc:
                self._logger.warning(f"MVStore: failed to load: {exc}")

    def _save(self):
        try:
            self._persist_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._persist_path, "w", encoding="utf-8") as f:
                json.dump(self._tasks, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            self._logger.warning(f"MVStore: failed to persist: {exc}")

    # ------------------------------------------------------------------ public

    def create(
        self,
        clip_id: str,
        clip_title: str,
        mode: str,
        use_ref_images: bool,
        model: str,
        scene_duration: int,
        audio_url: str = "",
        duration: float = 0,
        tags: str = "",
        lyrics: str = "",
        highlight_duration: int = 60,
        highlight_start: int = 0,
    ) -> Dict[str, Any]:
        """创建一个新的 MV 生成任务"""
        mv_id = uuid.uuid4().hex[:16]
        record = {
            "mv_id": mv_id,
            "clip_id": clip_id,
            "clip_title": clip_title,
            "status": MV_STATUS_PENDING,
            "mode": mode,
            "use_ref_images": use_ref_images,
            "model": model,
            "scene_duration": scene_duration,
            "audio_url": audio_url,
            "duration": duration,
            "tags": tags,
            "lyrics": lyrics,
            "highlight_duration": highlight_duration,
            "highlight_start": highlight_start,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": None,
            "storyboard": [],
            "scenes": [],
            "error": None,
            "video_path": None,
        }
        with self._lock:
            self._tasks[mv_id] = record
            self._save()
        self._logger.info(f"MVStore: created MV task {mv_id} for clip {clip_id}")
        return dict(record)

    def get(self, mv_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            rec = self._tasks.get(mv_id)
            return dict(rec) if rec else None

    def list_all(self) -> List[Dict[str, Any]]:
        with self._lock:
            return [dict(r) for r in self._tasks.values()]

    def list_by_clip(self, clip_id: str) -> List[Dict[str, Any]]:
        with self._lock:
            return [
                dict(r) for r in self._tasks.values()
                if r.get("clip_id") == clip_id
            ]

    def get_active_ids(self) -> List[str]:
        with self._lock:
            return [
                mid for mid, rec in self._tasks.items()
                if rec.get("status") not in MV_TERMINAL
            ]

    def get_recoverable_tasks(self) -> List[Dict[str, Any]]:
        """返回所有处于可恢复状态的任务副本。"""
        with self._lock:
            return [
                dict(rec) for rec in self._tasks.values()
                if rec.get("status") in MV_RECOVERABLE
            ]

    def update_status(self, mv_id: str, status: str, error: Optional[str] = None):
        with self._lock:
            rec = self._tasks.get(mv_id)
            if rec:
                rec["status"] = status
                if error is not None:
                    rec["error"] = error
                if status in MV_TERMINAL:
                    rec["finished_at"] = datetime.now(timezone.utc).isoformat()
                self._save()

    def update_storyboard(self, mv_id: str, storyboard: List[Dict[str, Any]]):
        with self._lock:
            rec = self._tasks.get(mv_id)
            if rec:
                rec["storyboard"] = storyboard
                # 初始化 scenes 状态
                rec["scenes"] = [
                    {
                        "scene_index": s["scene_index"],
                        "status": "pending",
                        "operation_name": None,
                        "video_file": None,
                        "ref_image_file": None,
                    }
                    for s in storyboard
                ]
                self._save()

    def update_scene(self, mv_id: str, scene_index: int, updates: Dict[str, Any]):
        with self._lock:
            rec = self._tasks.get(mv_id)
            if rec and scene_index < len(rec.get("scenes", [])):
                rec["scenes"][scene_index].update(updates)
                self._save()

    def set_video_path(self, mv_id: str, path: str):
        with self._lock:
            rec = self._tasks.get(mv_id)
            if rec:
                rec["video_path"] = path
                self._save()

    def mark_all_active_interrupted(self) -> int:
        """将所有非终态任务标记为 INTERRUPTED。返回被标记的数量。"""
        count = 0
        with self._lock:
            for rec in self._tasks.values():
                if rec.get("status") not in MV_TERMINAL:
                    rec["status"] = MV_STATUS_INTERRUPTED
                    count += 1
            if count > 0:
                self._save()
        if count > 0:
            self._logger.info(f"MVStore: marked {count} active tasks as INTERRUPTED")
        return count

    def delete(self, mv_id: str) -> bool:
        """删除一个 MV 任务记录及其输出文件。返回是否成功删除。"""
        import shutil
        with self._lock:
            if mv_id not in self._tasks:
                return False
            del self._tasks[mv_id]
            self._save()
        # 在锁外删除文件目录
        mv_dir = self._mv_dir / mv_id
        if mv_dir.exists():
            try:
                shutil.rmtree(mv_dir)
            except Exception as exc:
                self._logger.warning(f"MVStore: failed to remove dir {mv_dir}: {exc}")
        self._logger.info(f"MVStore: deleted MV task {mv_id}")
        return True

    def get_mv_dir(self, mv_id: str) -> Path:
        """获取某个 MV 任务的输出目录"""
        d = self._mv_dir / mv_id
        d.mkdir(parents=True, exist_ok=True)
        return d


# ------------------------------------------------------------------ singleton

_store: Optional[MVStore] = None
_store_lock = threading.Lock()


def get_mv_store() -> MVStore:
    global _store
    if _store is None:
        with _store_lock:
            if _store is None:
                _store = MVStore()
    return _store
