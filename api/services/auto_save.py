"""
Auto-save service for downloading completed Suno clips to local disk.

Downloads MP3 audio and cover-art JPG for each clip in a finished task.
"""

import re
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

import requests

from src.config import get_config
from src.logger import get_logger


def _sanitize_filename(name: str) -> str:
    """Replace characters that are invalid in filenames."""
    # Remove or replace characters not safe for Windows/Linux filenames
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", name)
    sanitized = sanitized.strip(". ")
    return sanitized or "untitled"


class AutoSaver:
    """Downloads completed clip assets (MP3 + cover art) to the output directory."""

    def __init__(self, output_dir: Optional[Path] = None):
        cfg = get_config()
        self._output_dir = output_dir or cfg.output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)
        self._logger = get_logger()

    def save_clips(self, task_record: Dict[str, Any]) -> List[str]:
        """Download all clips from a finished task record.

        Args:
            task_record: A task dict containing a ``clips`` list.

        Returns:
            List of saved filenames (relative to output_dir).
        """
        clips = task_record.get("clips") or []
        saved: List[str] = []

        for clip in clips:
            if not isinstance(clip, dict):
                continue

            clip_id = clip.get("id", "unknown")
            title = clip.get("title") or "untitled"
            short_id = clip_id[:8]
            base_name = f"{_sanitize_filename(title)}_{short_id}"

            # --- MP3 audio ---
            audio_url = clip.get("audio_url")
            if audio_url:
                mp3_name = f"{base_name}.mp3"
                mp3_path = self._output_dir / mp3_name
                if mp3_path.exists():
                    self._logger.info(f"AutoSaver: skipping existing {mp3_name}")
                    saved.append(mp3_name)
                else:
                    if self._download(audio_url, mp3_path, stream=True):
                        saved.append(mp3_name)

            # --- Cover art JPG ---
            image_url = clip.get("image_large_url") or clip.get("image_url")
            if image_url:
                jpg_name = f"{base_name}.jpg"
                jpg_path = self._output_dir / jpg_name
                if jpg_path.exists():
                    self._logger.info(f"AutoSaver: skipping existing {jpg_name}")
                    saved.append(jpg_name)
                else:
                    if self._download(image_url, jpg_path, stream=False):
                        saved.append(jpg_name)

        return saved

    def _download(self, url: str, dest: Path, stream: bool = False) -> bool:
        """Download a URL to a local file. Returns True on success."""
        try:
            self._logger.info(f"AutoSaver: downloading {dest.name} from {url[:80]}...")
            resp = requests.get(url, stream=stream, timeout=120)
            resp.raise_for_status()

            with open(dest, "wb") as f:
                if stream:
                    for chunk in resp.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                else:
                    f.write(resp.content)

            self._logger.info(f"AutoSaver: saved {dest.name} ({dest.stat().st_size} bytes)")
            return True
        except Exception as exc:
            self._logger.error(f"AutoSaver: failed to download {url[:80]}: {exc}")
            # Clean up partial file
            if dest.exists():
                try:
                    dest.unlink()
                except OSError:
                    pass
            return False


# ------------------------------------------------------------------ singleton

_saver: Optional[AutoSaver] = None
_saver_lock = threading.Lock()


def get_auto_saver() -> AutoSaver:
    """Return the singleton AutoSaver instance."""
    global _saver
    if _saver is None:
        with _saver_lock:
            if _saver is None:
                _saver = AutoSaver()
    return _saver
