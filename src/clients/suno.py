"""
Suno 镜像站 API 客户端

基于 api.vectorengine.ai 的 REST API 封装。
"""

import time
import requests
from typing import Any, Dict, List, Optional

from ..config import get_config
from ..logger import get_logger


class SunoClient:
    """Suno 镜像站 API 客户端"""

    # 任务终态
    TERMINAL_STATUSES = {"SUCCESS", "FAILURE"}

    def __init__(self, timeout: int = 30):
        self.cfg = get_config()
        self.logger = get_logger()
        self.base_url = self.cfg.suno_base_url.rstrip("/")
        self.timeout = timeout

    def _headers(self) -> Dict[str, str]:
        return {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.cfg.suno_api_key}",
        }

    def _post(self, path: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        self.logger.debug(f"Suno POST {path}")
        resp = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
        try:
            data = resp.json()
        except Exception:
            resp.raise_for_status()
            return {"code": "error", "data": None, "message": resp.text[:500]}
        if not resp.ok:
            self.logger.warning(f"Suno POST {path} -> HTTP {resp.status_code}: {data}")
        return data

    def _get(self, path: str) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        self.logger.debug(f"Suno GET {path}")
        resp = requests.get(url, headers=self._headers(), timeout=self.timeout)
        try:
            data = resp.json()
        except Exception:
            resp.raise_for_status()
            return {"code": "error", "data": None, "message": resp.text[:500]}
        if not resp.ok:
            self.logger.warning(f"Suno GET {path} -> HTTP {resp.status_code}: {data}")
        return data

    # ============================================================ 任务提交
    def generate_music_inspiration(
        self,
        description: str,
        make_instrumental: bool = False,
        mv: Optional[str] = None,
    ) -> Dict[str, Any]:
        """灵感模式生成音乐

        Args:
            description: 创作描述 (如 "一首关于春天的轻快民谣")
            make_instrumental: 是否纯音乐
            mv: 模型版本

        Returns:
            {"code": "success", "data": "<task_id>", "message": ""}
        """
        payload = {
            "gpt_description_prompt": description,
            "make_instrumental": make_instrumental,
            "mv": mv or self.cfg.suno_model,
            "prompt": "",
        }
        result = self._post("/suno/submit/music", payload)
        self.logger.log_event("suno_submit_inspiration", {
            "description": description,
            "response": result,
        })
        return result

    def generate_music_custom(
        self,
        prompt: str,
        title: str,
        tags: str = "",
        mv: Optional[str] = None,
        negative_tags: str = "",
        make_instrumental: bool = False,
    ) -> Dict[str, Any]:
        """自定义模式生成音乐（提供歌词）

        Args:
            prompt: 完整歌词
            title: 歌曲标题
            tags: 风格标签 (逗号分隔)
            mv: 模型版本
            negative_tags: 不希望的风格
            make_instrumental: 是否纯音乐

        Returns:
            {"code": "success", "data": "<task_id>", "message": ""}
        """
        payload = {
            "prompt": prompt,
            "title": title,
            "tags": tags,
            "mv": mv or self.cfg.suno_model,
            "negative_tags": negative_tags,
            "make_instrumental": make_instrumental,
            "continue_at": None,
            "continue_clip_id": "",
            "task": "",
        }
        result = self._post("/suno/submit/music", payload)
        self.logger.log_event("suno_submit_custom", {
            "title": title,
            "tags": tags,
            "response": result,
        })
        return result

    def generate_music_continue(
        self,
        prompt: str,
        title: str,
        tags: str,
        continue_clip_id: str,
        continue_at: float,
        mv: Optional[str] = None,
    ) -> Dict[str, Any]:
        """续写模式"""
        payload = {
            "prompt": prompt,
            "title": title,
            "tags": tags,
            "mv": mv or self.cfg.suno_model,
            "continue_at": continue_at,
            "continue_clip_id": continue_clip_id,
            "task": "extend",
        }
        result = self._post("/suno/submit/music", payload)
        self.logger.log_event("suno_submit_continue", {
            "continue_clip_id": continue_clip_id,
            "response": result,
        })
        return result

    # ============================================================ 查询
    def query_task(self, task_id: str) -> Dict[str, Any]:
        """查询单个任务"""
        return self._get(f"/suno/fetch/{task_id}")

    def batch_query(self, task_ids: List[str]) -> Dict[str, Any]:
        """批量查询任务"""
        return self._post("/suno/fetch", {"ids": task_ids})

    def get_wav_url(self, clip_id: str) -> Dict[str, Any]:
        """获取 WAV 下载信息"""
        return self._get(f"/suno/act/wav/{clip_id}")

    def get_feed(self, clip_id: str) -> Dict[str, Any]:
        """获取场景详情"""
        return self._get(f"/suno/feed/{clip_id}")

    # ============================================================ 轮询
    def wait_for_task(
        self,
        task_id: str,
        poll_interval: float = 10.0,
        max_wait: float = 600.0,
    ) -> Dict[str, Any]:
        """轮询任务直到完成

        Args:
            task_id: 任务 ID
            poll_interval: 轮询间隔 (秒)
            max_wait: 最大等待时间 (秒)

        Returns:
            最终的任务响应
        """
        elapsed = 0.0
        while elapsed < max_wait:
            result = self.query_task(task_id)
            data = result.get("data", {})

            # data 可能是包含 status 的 dict，也可能是 task_id string
            if isinstance(data, dict):
                status = data.get("status", "")
                if status in self.TERMINAL_STATUSES:
                    self.logger.info(f"任务 {task_id} 完成: {status}")
                    return result
                self.logger.info(f"任务 {task_id} 状态: {status}，等待中...")
            else:
                self.logger.info(f"任务 {task_id} 等待中... (data={str(data)[:100]})")

            time.sleep(poll_interval)
            elapsed += poll_interval

        self.logger.warning(f"任务 {task_id} 超时 ({max_wait}s)")
        return {"code": "timeout", "data": None, "message": f"等待超过 {max_wait}s"}
