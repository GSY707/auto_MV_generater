"""
Vertex AI 认证辅助模块

自动获取和刷新 OAuth2 Access Token，支持三种方式:
  1. google-auth (ADC - Application Default Credentials)
  2. gcloud auth print-access-token
  3. 静态 token (从 .env 配置)

OAuth2 token 有效期约 1 小时，此模块在过期前自动刷新。
"""

import shutil
import subprocess
import threading
import time
from typing import Optional

from ..config import get_config
from ..logger import get_logger


class VertexAuthProvider:
    """Vertex AI OAuth2 Access Token 提供器"""

    # Token 在过期前 5 分钟刷新
    REFRESH_MARGIN = 300

    def __init__(self):
        self._logger = get_logger()
        self._lock = threading.Lock()
        self._token: Optional[str] = None
        self._expires_at: float = 0
        self._method: Optional[str] = None

    def get_access_token(self) -> str:
        """获取有效的 access token，必要时自动刷新"""
        with self._lock:
            if self._token and time.time() < self._expires_at:
                return self._token

            # 尝试各种方式获取 token
            token = self._try_google_auth()
            if not token:
                token = self._try_gcloud()
            if not token:
                token = self._try_static()
            if not token:
                raise RuntimeError(
                    "无法获取 Vertex AI access token。\n"
                    "请运行 'gcloud auth application-default login' 或在 .env 中设置 VERTEX_AI_ACCESS_TOKEN"
                )

            self._token = token
            return token

    def _try_google_auth(self) -> Optional[str]:
        """通过 google-auth 库的 ADC 获取 token"""
        try:
            import google.auth
            import google.auth.transport.requests

            credentials, project = google.auth.default(
                scopes=["https://www.googleapis.com/auth/cloud-platform"]
            )
            credentials.refresh(google.auth.transport.requests.Request())

            self._expires_at = time.time() + 3300  # ~55 分钟
            self._method = "google-auth ADC"
            self._logger.info(f"VertexAuth: 通过 google-auth ADC 获取 token (project={project})")
            return credentials.token
        except Exception as exc:
            self._logger.debug(f"VertexAuth: google-auth ADC 不可用: {exc}")
            return None

    def _try_gcloud(self) -> Optional[str]:
        """通过 gcloud CLI 获取 token"""
        try:
            # Windows 上 gcloud 可能是 .CMD 文件，需要用 shutil.which 找到完整路径
            gcloud_path = shutil.which("gcloud")
            if not gcloud_path:
                self._logger.debug("VertexAuth: gcloud 不在 PATH 中")
                return None

            result = subprocess.run(
                [gcloud_path, "auth", "print-access-token"],
                capture_output=True,
                text=True,
                timeout=15,
                shell=True,  # Windows 上 .CMD 文件需要 shell=True
            )
            if result.returncode == 0 and result.stdout.strip():
                token = result.stdout.strip()
                self._expires_at = time.time() + 3300  # ~55 分钟
                self._method = "gcloud CLI"
                self._logger.info("VertexAuth: 通过 gcloud CLI 获取 token")
                return token
            else:
                self._logger.debug(f"VertexAuth: gcloud 返回错误: {result.stderr[:200]}")
        except Exception as exc:
            self._logger.debug(f"VertexAuth: gcloud CLI 不可用: {exc}")
        return None

    def _try_static(self) -> Optional[str]:
        """使用 .env 中的静态 token"""
        cfg = get_config()
        token = cfg.vertex_ai_access_token
        if token:
            # 静态 token 不知道过期时间，设为 30 分钟后重新尝试
            self._expires_at = time.time() + 1800
            self._method = "static (.env)"
            self._logger.info("VertexAuth: 使用 .env 中的静态 token (可能已过期)")
            return token
        return None

    def invalidate(self):
        """标记当前 token 无效，下次调用时强制刷新"""
        with self._lock:
            self._token = None
            self._expires_at = 0

    @property
    def method(self) -> Optional[str]:
        return self._method


# ------------------------------------------------------------------ singleton

_provider: Optional[VertexAuthProvider] = None
_provider_lock = threading.Lock()


def get_vertex_auth() -> VertexAuthProvider:
    """获取全局 VertexAuthProvider 实例"""
    global _provider
    if _provider is None:
        with _provider_lock:
            if _provider is None:
                _provider = VertexAuthProvider()
    return _provider
