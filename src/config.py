"""
Music Agent 配置管理
"""

import os
from pathlib import Path
from typing import Optional


class Config:
    """全局配置"""

    DEFAULT_PROJECT_ROOT = Path(__file__).parent.parent
    DEFAULT_ENV_FILE = DEFAULT_PROJECT_ROOT / ".env"

    def __init__(self):
        # --- Gemini LLM ---
        self.gemini_backend: str = os.getenv("GEMINI_BACKEND", "ai_studio")
        self.google_ai_studio_key: str = os.getenv("GOOGLE_AI_STUDIO_KEY", "")
        self.vertex_ai_project_id: str = os.getenv("VERTEX_AI_PROJECT_ID", "")
        self.vertex_ai_location: str = os.getenv("VERTEX_AI_LOCATION", "us-central1")
        self.vertex_ai_access_token: str = os.getenv("VERTEX_AI_ACCESS_TOKEN", "")
        self.gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

        # --- Suno 镜像站 ---
        self.suno_api_key: str = os.getenv("SUNO_API_KEY", "")
        self.suno_base_url: str = os.getenv("SUNO_BASE_URL", "https://api.vectorengine.ai")
        self.suno_model: str = os.getenv("SUNO_MODEL", "chirp-v5")

        # --- Veo 视频生成 ---
        self.veo_model: str = os.getenv("VEO_MODEL", "veo-3.0-fast-generate-preview")
        self.veo_scene_duration: int = int(os.getenv("VEO_SCENE_DURATION", "8"))
        self.veo_resolution: str = os.getenv("VEO_RESOLUTION", "1080p")

        # --- Gemini Image ---
        self.gemini_image_model: str = os.getenv("GEMINI_IMAGE_MODEL", "gemini-2.5-flash-image")

        # --- Agent ---
        self.max_agent_steps: int = int(os.getenv("MAX_AGENT_STEPS", "15"))
        self.agent_temperature: float = float(os.getenv("AGENT_TEMPERATURE", "0.7"))
        self.max_output_tokens: int = int(os.getenv("MAX_OUTPUT_TOKENS", "8192"))

        # --- 通用 ---
        self.log_level: str = os.getenv("LOG_LEVEL", "INFO")
        self.project_root: Path = self.DEFAULT_PROJECT_ROOT
        self.output_dir: Path = Path(os.getenv("OUTPUT_DIR", self.project_root / "output"))
        self.log_dir: Path = self.project_root / "logs"

        self._ensure_dirs()

    def _ensure_dirs(self):
        for d in [self.output_dir, self.log_dir]:
            d.mkdir(parents=True, exist_ok=True)

    @classmethod
    def from_env(cls, env_file: Optional[Path] = None) -> "Config":
        from dotenv import load_dotenv

        env_file = env_file or cls.DEFAULT_ENV_FILE
        if env_file.exists():
            load_dotenv(env_file, override=True)
        return cls()

    def validate(self) -> bool:
        ok = True
        if self.gemini_backend == "vertex_ai":
            if not self.vertex_ai_project_id:
                print("[Config] VERTEX_AI_PROJECT_ID 未设置，将回退到 ai_studio")
                self.gemini_backend = "ai_studio"
            if not self.vertex_ai_access_token:
                print("[Config] VERTEX_AI_ACCESS_TOKEN 未设置，将回退到 ai_studio")
                self.gemini_backend = "ai_studio"
        if self.gemini_backend == "ai_studio" and not self.google_ai_studio_key:
            print("[Config] 错误: GOOGLE_AI_STUDIO_KEY 未设置")
            ok = False
        if not self.suno_api_key:
            print("[Config] 错误: SUNO_API_KEY 未设置")
            ok = False
        return ok

    def __repr__(self) -> str:
        return (
            f"Config(backend={self.gemini_backend}, model={self.gemini_model}, "
            f"suno_model={self.suno_model})"
        )


_config: Optional[Config] = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = Config.from_env()
    return _config
