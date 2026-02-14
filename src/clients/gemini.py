"""
Google Gemini API 客户端

支持两种后端:
  - ai_studio: 通过 API Key 调用 Google AI Studio
  - vertex_ai: 通过 Access Token 调用 Google Vertex AI
两种后端使用相同的 generateContent 请求/响应格式。
"""

import time
import json
import requests
from typing import Any, Dict, List, Optional

from ..config import get_config
from ..logger import get_logger


class GeminiClient:
    """Gemini REST API 客户端，支持 function calling"""

    def __init__(self, max_retries: int = 3, timeout: int = 120):
        self.cfg = get_config()
        self.logger = get_logger()
        self.max_retries = max_retries
        self.timeout = timeout
        self.total_tokens = 0
        self.total_requests = 0

    # ------------------------------------------------------------------ URL
    def _build_url(self, stream: bool = False) -> str:
        model = self.cfg.gemini_model
        method = "streamGenerateContent" if stream else "generateContent"

        if self.cfg.gemini_backend == "vertex_ai":
            proj = self.cfg.vertex_ai_project_id
            loc = self.cfg.vertex_ai_location
            return (
                f"https://{loc}-aiplatform.googleapis.com/v1/"
                f"projects/{proj}/locations/{loc}/"
                f"publishers/google/models/{model}:{method}"
            )
        else:
            key = self.cfg.google_ai_studio_key
            return (
                f"https://generativelanguage.googleapis.com/v1beta/"
                f"models/{model}:{method}?key={key}"
            )

    def _build_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.cfg.gemini_backend == "vertex_ai":
            headers["Authorization"] = f"Bearer {self.cfg.vertex_ai_access_token}"
        return headers

    # -------------------------------------------------------- generate_content
    def generate_content(
        self,
        contents: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
        temperature: Optional[float] = None,
        max_output_tokens: Optional[int] = None,
    ) -> Dict[str, Any]:
        """调用 Gemini generateContent API

        Args:
            contents: 对话内容 (Gemini 格式 parts)
            tools: 函数声明列表
            system_instruction: 系统指令
            temperature: 采样温度
            max_output_tokens: 最大输出 token

        Returns:
            Gemini API 原始响应 dict
        """
        url = self._build_url()
        headers = self._build_headers()

        payload: Dict[str, Any] = {"contents": contents}

        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        if tools:
            payload["tools"] = tools

        gen_cfg: Dict[str, Any] = {}
        if temperature is not None:
            gen_cfg["temperature"] = temperature
        if max_output_tokens is not None:
            gen_cfg["maxOutputTokens"] = max_output_tokens
        if gen_cfg:
            payload["generationConfig"] = gen_cfg

        last_error = None
        for attempt in range(self.max_retries):
            try:
                self.logger.debug(f"Gemini API 请求 (attempt {attempt + 1})")
                resp = requests.post(url, headers=headers, json=payload, timeout=self.timeout)

                if resp.status_code == 200:
                    result = resp.json()
                    self.total_requests += 1
                    usage = result.get("usageMetadata", {})
                    self.total_tokens += usage.get("totalTokenCount", 0)
                    return result

                last_error = f"HTTP {resp.status_code}: {resp.text[:500]}"
                self.logger.warning(f"Gemini API 错误: {last_error}")

                if 400 <= resp.status_code < 500 and resp.status_code != 429:
                    raise RuntimeError(last_error)

            except requests.Timeout:
                last_error = f"请求超时 ({self.timeout}s)"
                self.logger.warning(last_error)
            except RuntimeError:
                raise
            except Exception as e:
                last_error = str(e)
                self.logger.warning(f"Gemini API 异常: {last_error}")

            if attempt < self.max_retries - 1:
                wait = 2 ** attempt
                self.logger.info(f"等待 {wait}s 后重试...")
                time.sleep(wait)

        raise RuntimeError(f"Gemini API 调用失败 (重试 {self.max_retries} 次): {last_error}")

    # -------------------------------------------------------- 便捷方法
    def chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None,
        system_instruction: Optional[str] = None,
    ) -> Dict[str, Any]:
        """发送对话并返回模型响应的 content dict

        Returns:
            {"parts": [...], "role": "model"} 形式的 dict
        """
        result = self.generate_content(
            contents=messages,
            tools=tools,
            system_instruction=system_instruction,
            temperature=self.cfg.agent_temperature,
            max_output_tokens=self.cfg.max_output_tokens,
        )
        candidates = result.get("candidates", [])
        if not candidates:
            raise RuntimeError(f"Gemini 未返回候选结果: {json.dumps(result, ensure_ascii=False)[:500]}")
        return candidates[0]["content"]

    @staticmethod
    def extract_text(content: Dict[str, Any]) -> str:
        """从 Gemini content 中提取纯文本"""
        parts = content.get("parts", [])
        texts = [p["text"] for p in parts if "text" in p]
        return "\n".join(texts)

    @staticmethod
    def extract_function_calls(content: Dict[str, Any]) -> List[Dict[str, Any]]:
        """从 Gemini content 中提取 functionCall"""
        parts = content.get("parts", [])
        return [p["functionCall"] for p in parts if "functionCall" in p]

    @staticmethod
    def make_user_message(text: str) -> Dict[str, Any]:
        return {"role": "user", "parts": [{"text": text}]}

    @staticmethod
    def make_model_message(content: Dict[str, Any]) -> Dict[str, Any]:
        """重新包装 content 为消息格式（保留 parts 原样）"""
        return {"role": "model", "parts": content.get("parts", [])}

    @staticmethod
    def make_function_response(name: str, response: Any) -> Dict[str, Any]:
        return {
            "role": "user",
            "parts": [{
                "functionResponse": {
                    "name": name,
                    "response": {"content": response},
                }
            }],
        }
