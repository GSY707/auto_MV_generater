"""
Google Veo API 客户端 (Vertex AI)

通过 predictLongRunning / fetchPredictOperation 生成视频。
Veo 仅支持 Vertex AI，不支持 AI Studio。
使用 VertexAuthProvider 自动获取/刷新 OAuth2 Access Token。
"""

import base64
import time
import requests
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

from ..config import get_config
from ..logger import get_logger
from .vertex_auth import get_vertex_auth


class VeoClient:
    """Veo REST API 客户端，使用 Vertex AI Long Running Operation 模式"""

    DEFAULT_MODEL = "veo-3.0-fast-generate-preview"
    SUPPORTED_MODELS = [
        "veo-3.1-fast-generate-preview",
        "veo-3.1-fast-generate-001",
        "veo-3.0-fast-generate-preview",
    ]

    def __init__(self, timeout: int = 60):
        self.cfg = get_config()
        self.logger = get_logger()
        self.timeout = timeout
        self._auth = get_vertex_auth()

    # ------------------------------------------------------------------ URL helpers

    def _base_url(self, model: Optional[str] = None) -> str:
        proj = self.cfg.vertex_ai_project_id
        loc = self.cfg.vertex_ai_location
        m = model or self.cfg.veo_model
        return (
            f"https://{loc}-aiplatform.googleapis.com/v1/"
            f"projects/{proj}/locations/{loc}/"
            f"publishers/google/models/{m}"
        )

    def _headers(self) -> Dict[str, str]:
        token = self._auth.get_access_token()
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }

    # ------------------------------------------------------------------ submit

    def submit_text_to_video(
        self,
        prompt: str,
        duration: int = 8,
        resolution: str = "1080p",
        aspect_ratio: str = "16:9",
        model: Optional[str] = None,
    ) -> str:
        """提交文本到视频生成任务

        Args:
            prompt: 视频描述文本
            duration: 时长 (4, 6, 或 8 秒)
            resolution: 分辨率 (720p 或 1080p)
            aspect_ratio: 宽高比
            model: 模型 ID

        Returns:
            operation_name: 长时间运行操作的名称
        """
        url = f"{self._base_url(model)}:predictLongRunning"
        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "aspectRatio": aspect_ratio,
                "durationSeconds": duration,
                "generateAudio": False,
                "resolution": resolution,
                "sampleCount": 1,
            },
        }
        self.logger.info(f"Veo: 提交文本到视频 (duration={duration}s, model={model or self.cfg.veo_model})")
        return self._submit(url, payload)

    def submit_image_to_video(
        self,
        prompt: str,
        image_base64: str,
        image_mime: str = "image/jpeg",
        duration: int = 8,
        resolution: str = "1080p",
        aspect_ratio: str = "16:9",
        model: Optional[str] = None,
    ) -> str:
        """提交图片+文本到视频生成任务

        Args:
            prompt: 视频描述文本
            image_base64: 参考图片的 base64 编码
            image_mime: 图片 MIME 类型
            duration: 时长秒数
            resolution: 分辨率
            aspect_ratio: 宽高比
            model: 模型 ID

        Returns:
            operation_name
        """
        url = f"{self._base_url(model)}:predictLongRunning"
        payload = {
            "instances": [{
                "prompt": prompt,
                "image": {
                    "bytesBase64Encoded": image_base64,
                    "mimeType": image_mime,
                },
            }],
            "parameters": {
                "aspectRatio": aspect_ratio,
                "durationSeconds": duration,
                "generateAudio": False,
                "resolution": resolution,
                "sampleCount": 1,
            },
        }
        self.logger.info(f"Veo: 提交图片到视频 (duration={duration}s)")
        return self._submit(url, payload)

    def _submit(self, url: str, payload: Dict[str, Any]) -> str:
        """发送请求并返回 operation_name，支持 token 自动刷新"""
        for attempt in range(2):
            resp = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
            if resp.status_code == 401 and attempt == 0:
                self.logger.warning("Veo: 收到 401，尝试刷新 token...")
                self._auth.invalidate()
                continue
            break

        if resp.status_code != 200:
            error_msg = f"Veo submit 失败: HTTP {resp.status_code}: {resp.text[:500]}"
            self.logger.error(error_msg)
            raise RuntimeError(error_msg)

        data = resp.json()
        operation_name = data.get("name")
        if not operation_name:
            raise RuntimeError(f"Veo 响应中缺少 operation name: {data}")

        self.logger.info(f"Veo: 操作已提交 -> {operation_name}")
        return operation_name

    # ------------------------------------------------------------------ poll

    def poll_operation(
        self, operation_name: str, model: Optional[str] = None
    ) -> Tuple[bool, Dict[str, Any]]:
        """查询长时间运行操作的状态

        Args:
            operation_name: 操作名称
            model: 模型 ID

        Returns:
            (done, result_dict)
            done=True 时 result_dict 包含 videos 列表
        """
        url = f"{self._base_url(model)}:fetchPredictOperation"
        payload = {"operationName": operation_name}

        for attempt in range(2):
            resp = requests.post(url, headers=self._headers(), json=payload, timeout=self.timeout)
            if resp.status_code == 401 and attempt == 0:
                self.logger.warning("Veo poll: 收到 401，尝试刷新 token...")
                self._auth.invalidate()
                continue
            break

        if resp.status_code != 200:
            error_msg = f"Veo poll 失败: HTTP {resp.status_code}: {resp.text[:500]}"
            self.logger.warning(error_msg)
            raise RuntimeError(error_msg)

        data = resp.json()
        done = data.get("done", False)

        if done:
            response = data.get("response", {})
            error = data.get("error")
            if error:
                raise RuntimeError(f"Veo 操作失败: {error}")
            return True, response
        else:
            return False, data

    def wait_for_operation(
        self,
        operation_name: str,
        model: Optional[str] = None,
        poll_interval: float = 15.0,
        max_wait: float = 600.0,
    ) -> Dict[str, Any]:
        """轮询操作直到完成

        Returns:
            response dict，包含 videos 列表
        """
        elapsed = 0.0
        while elapsed < max_wait:
            done, result = self.poll_operation(operation_name, model)
            if done:
                return result
            self.logger.info(f"Veo: 操作进行中... (已等待 {elapsed:.0f}s)")
            time.sleep(poll_interval)
            elapsed += poll_interval

        raise RuntimeError(f"Veo 操作超时 ({max_wait}s): {operation_name}")

    # ------------------------------------------------------------------ 工具方法

    @staticmethod
    def save_video_from_response(
        response: Dict[str, Any], output_path: Path
    ) -> Optional[Path]:
        """从 Veo 响应中提取视频并保存到文件

        Args:
            response: poll 完成后的 response dict
            output_path: 保存路径 (不含扩展名也行，会自动加 .mp4)

        Returns:
            保存的文件路径，或 None
        """
        videos = response.get("videos", [])
        if not videos:
            # 可能被内容审核过滤
            filtered = response.get("raiMediaFilteredReasons")
            if filtered:
                from ..logger import get_logger
                get_logger().warning(f"Veo: 视频被内容过滤: {filtered}")
            return None

        video = videos[0]
        b64_data = video.get("bytesBase64Encoded")
        if not b64_data:
            return None

        output_path = Path(output_path)
        if output_path.suffix != ".mp4":
            output_path = output_path.with_suffix(".mp4")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        video_bytes = base64.b64decode(b64_data)
        output_path.write_bytes(video_bytes)

        return output_path
