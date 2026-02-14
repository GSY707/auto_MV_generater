"""
Gemini Image 生成客户端

使用 gemini-2.5-flash-image (Nano Banana) 模型生成参考图片。
支持 AI Studio 和 Vertex AI 两种后端。
"""

import base64
import requests
from typing import Any, Dict, Optional, Tuple

from ..config import get_config
from ..logger import get_logger


class GeminiImageClient:
    """Gemini Image API 客户端，用于生成参考图片"""

    DEFAULT_MODEL = "gemini-2.5-flash-image"

    def __init__(self, timeout: int = 120):
        self.cfg = get_config()
        self.logger = get_logger()
        self.timeout = timeout
        self.model = self.cfg.gemini_image_model

    def _build_url(self) -> str:
        if self.cfg.gemini_backend == "vertex_ai":
            proj = self.cfg.vertex_ai_project_id
            loc = self.cfg.vertex_ai_location
            return (
                f"https://{loc}-aiplatform.googleapis.com/v1/"
                f"projects/{proj}/locations/{loc}/"
                f"publishers/google/models/{self.model}:generateContent"
            )
        else:
            key = self.cfg.google_ai_studio_key
            return (
                f"https://generativelanguage.googleapis.com/v1beta/"
                f"models/{self.model}:generateContent?key={key}"
            )

    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.cfg.gemini_backend == "vertex_ai":
            headers["Authorization"] = f"Bearer {self.cfg.vertex_ai_access_token}"
        return headers

    def generate_image(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
    ) -> Optional[Tuple[bytes, str]]:
        """生成图片

        Args:
            prompt: 图片描述
            aspect_ratio: 宽高比

        Returns:
            (image_bytes, mime_type) 或 None
        """
        url = self._build_url()
        headers = self._build_headers()

        payload = {
            "contents": {
                "role": "USER",
                "parts": [{"text": prompt}],
            },
            "generationConfig": {
                "responseModalities": ["IMAGE"],
                "imageConfig": {
                    "aspectRatio": aspect_ratio,
                },
            },
        }

        self.logger.info(f"GeminiImage: 生成图片 (model={self.model})")
        resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)

        if resp.status_code != 200:
            self.logger.error(f"GeminiImage: HTTP {resp.status_code}: {resp.text[:500]}")
            return None

        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            self.logger.warning("GeminiImage: 没有返回候选结果")
            return None

        parts = candidates[0].get("content", {}).get("parts", [])
        for part in parts:
            inline = part.get("inlineData")
            if inline and inline.get("data"):
                image_bytes = base64.b64decode(inline["data"])
                mime_type = inline.get("mimeType", "image/png")
                self.logger.info(f"GeminiImage: 成功生成图片 ({len(image_bytes)} bytes)")
                return image_bytes, mime_type

        self.logger.warning("GeminiImage: 响应中没有图片数据")
        return None

    def generate_image_base64(
        self,
        prompt: str,
        aspect_ratio: str = "16:9",
    ) -> Optional[Tuple[str, str]]:
        """生成图片并返回 base64

        Returns:
            (base64_string, mime_type) 或 None
        """
        result = self.generate_image(prompt, aspect_ratio)
        if result is None:
            return None
        image_bytes, mime_type = result
        return base64.b64encode(image_bytes).decode("ascii"), mime_type
