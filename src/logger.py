"""
Music Agent 日志系统
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from .config import get_config


class Logger:
    def __init__(self, log_dir: Optional[Path] = None):
        cfg = get_config()
        self.log_dir = Path(log_dir or cfg.log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_file = self.log_dir / f"session_{self.session_id}.jsonl"

        log_level = getattr(logging, cfg.log_level, logging.INFO)
        self._logger = logging.getLogger("music_agent")
        self._logger.setLevel(log_level)
        if not self._logger.handlers:
            fh = logging.FileHandler(self.log_dir / f"debug_{self.session_id}.log", encoding="utf-8")
            ch = logging.StreamHandler()
            fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            fh.setFormatter(fmt)
            ch.setFormatter(fmt)
            fh.setLevel(log_level)
            ch.setLevel(log_level)
            self._logger.addHandler(fh)
            self._logger.addHandler(ch)

    def _write(self, record: Dict[str, Any]):
        record["timestamp"] = datetime.now().isoformat()
        with open(self.session_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    def info(self, msg: str):
        self._logger.info(msg)

    def debug(self, msg: str):
        self._logger.debug(msg)

    def warning(self, msg: str):
        self._logger.warning(msg)

    def error(self, msg: str):
        self._logger.error(msg)

    def log_event(self, event: str, data: Dict[str, Any]):
        self._write({"event": event, **data})
        self._logger.debug(f"[{event}] {str(data)[:200]}")


_logger: Optional[Logger] = None


def get_logger() -> Logger:
    global _logger
    if _logger is None:
        _logger = Logger()
    return _logger
