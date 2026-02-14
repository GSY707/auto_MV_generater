"""
Recommendation service powered by Gemini.

Generates contextual music creation suggestions based on user profile
(history of clicked/dismissed recommendations and past creations).
"""

import json
import threading
from typing import Any, Dict, List, Optional, Set

from src.clients.gemini import GeminiClient
from src.logger import get_logger

RECOMMENDATION_PROMPT = """\
你是一个音乐创作灵感推荐引擎。根据用户画像，生成音乐创作建议。

用户画像:
{profile}

请生成 {count} 条音乐创作灵感推荐。每条推荐是一个简短的音乐描述（15-30字），
用户可以直接作为音乐生成的描述文本。

要求：
- 覆盖不同风格和主题
- 简洁有吸引力
- 不要和用户已点击过的推荐重复
- 如果有用户历史创作，参考其偏好但也要有新意

请严格输出 JSON 数组，不要包含其他文本：
["推荐1", "推荐2", ...]
"""

# Default recommendations to use as fallback
DEFAULT_RECOMMENDATIONS = [
    "一首关于夏日海滩的轻快流行歌曲",
    "深夜城市漫步的 Lo-Fi 电子音乐",
    "中国风古筝配现代 R&B 节奏",
    "雨天独处时听的慵懒爵士",
    "公路旅行的摇滚乐，带有吉他solo",
    "温柔的睡前民谣，木吉他伴奏",
    "充满能量的健身 EDM 音乐",
    "春天樱花下的日系清新流行",
    "赛博朋克风格的合成器音乐",
    "星空下的钢琴独奏曲",
    "复古迪斯科风格的舞曲",
    "海边日落时的 Bossa Nova",
]

# Default chat prompt suggestions
DEFAULT_CHAT_PROMPTS = [
    "帮我写一首关于旅行的歌",
    "推荐一些适合夜晚的音乐风格",
    "我想做一首EDM，有什么建议？",
    "帮我分析一下流行歌曲的结构",
    "什么风格适合表达思念的情感？",
    "帮我写一段朗朗上口的副歌",
    "推荐一些小众但好听的音乐风格",
    "如何让歌词更有画面感？",
]


class RecommendationService:
    """Manages personalized recommendations with click tracking."""

    def __init__(self):
        self._gemini = GeminiClient()
        self._logger = get_logger()
        # Track clicked recommendations per context
        self._clicked_create: Set[str] = set()
        self._clicked_chat: Set[str] = set()
        # Cache current recommendations
        self._current_create: List[str] = []
        self._current_chat: List[str] = []
        # User creation history (for profile)
        self._creation_history: List[Dict[str, Any]] = []

    def get_create_recommendations(self, count: int = 4) -> List[str]:
        """Get recommendation chips for the Create page."""
        # Filter out clicked ones
        available = [r for r in self._current_create if r not in self._clicked_create]
        if len(available) >= count:
            return available[:count]

        # Need to generate more
        try:
            new_recs = self._generate_recommendations(count + 4, "create")
            new_recs = [r for r in new_recs if r not in self._clicked_create]
            self._current_create = new_recs
            return new_recs[:count]
        except Exception as exc:
            self._logger.warning(f"RecommendationService: generate failed: {exc}")
            # Fallback to defaults
            available = [r for r in DEFAULT_RECOMMENDATIONS if r not in self._clicked_create]
            if len(available) < count:
                self._clicked_create.clear()
                available = list(DEFAULT_RECOMMENDATIONS)
            return available[:count]

    def get_chat_recommendations(self, count: int = 4) -> List[str]:
        """Get recommendation chips for the Chat page."""
        available = [r for r in self._current_chat if r not in self._clicked_chat]
        if len(available) >= count:
            return available[:count]

        # Need to generate more
        try:
            new_recs = self._generate_chat_recommendations(count + 4)
            new_recs = [r for r in new_recs if r not in self._clicked_chat]
            self._current_chat = new_recs
            return new_recs[:count]
        except Exception as exc:
            self._logger.warning(f"RecommendationService: chat generate failed: {exc}")
            available = [r for r in DEFAULT_CHAT_PROMPTS if r not in self._clicked_chat]
            if len(available) < count:
                self._clicked_chat.clear()
                available = list(DEFAULT_CHAT_PROMPTS)
            return available[:count]

    def mark_clicked(self, text: str, context: str = "create"):
        """Mark a recommendation as clicked so it won't appear again."""
        if context == "create":
            self._clicked_create.add(text)
        else:
            self._clicked_chat.add(text)

    def add_creation_history(self, params: Dict[str, Any]):
        """Record a creation event for user profiling."""
        self._creation_history.append(params)
        # Keep last 20
        if len(self._creation_history) > 20:
            self._creation_history = self._creation_history[-20:]

    def _build_profile(self) -> str:
        """Build a user profile string from history."""
        if not self._creation_history:
            return "新用户，没有历史记录。"

        parts = ["用户最近的创作历史:"]
        for h in self._creation_history[-5:]:
            desc = h.get("description", "") or h.get("tags", "") or h.get("title", "")
            if desc:
                parts.append(f"- {desc}")

        if self._clicked_create:
            parts.append(f"\n已点击过的推荐（不要重复）: {', '.join(list(self._clicked_create)[-10:])}")

        return "\n".join(parts)

    def _generate_recommendations(self, count: int, context: str) -> List[str]:
        """Use Gemini to generate personalized recommendations."""
        profile = self._build_profile()
        prompt = RECOMMENDATION_PROMPT.format(profile=profile, count=count)

        content = self._gemini.chat(
            messages=[GeminiClient.make_user_message(prompt)],
            system_instruction="你是一个音乐推荐引擎，只输出JSON数组。",
        )
        text = GeminiClient.extract_text(content).strip()

        # Parse JSON
        return self._parse_json_list(text)

    def _generate_chat_recommendations(self, count: int) -> List[str]:
        """Generate chat prompt recommendations."""
        profile = self._build_profile()
        prompt = f"""根据用户画像生成 {count} 条AI音乐助手的对话开场白建议。
每条是一个用户可能想问AI音乐助手的问题或请求（10-20字）。

用户画像:
{profile}

已用过的建议（不要重复）: {', '.join(list(self._clicked_chat)[-10:])}

请严格输出 JSON 数组：["建议1", "建议2", ...]"""

        content = self._gemini.chat(
            messages=[GeminiClient.make_user_message(prompt)],
            system_instruction="你是一个音乐助手推荐引擎，只输出JSON数组。",
        )
        text = GeminiClient.extract_text(content).strip()
        return self._parse_json_list(text)

    @staticmethod
    def _parse_json_list(text: str) -> List[str]:
        """Parse a JSON array of strings from text."""
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        try:
            data = json.loads(text)
            if isinstance(data, list):
                return [str(item) for item in data if isinstance(item, str)]
        except json.JSONDecodeError:
            pass

        # Try to find JSON array
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            try:
                data = json.loads(text[start:end + 1])
                if isinstance(data, list):
                    return [str(item) for item in data if isinstance(item, str)]
            except json.JSONDecodeError:
                pass

        return []


# ------------------------------------------------------------------ singleton

_service: Optional[RecommendationService] = None
_service_lock = threading.Lock()


def get_recommendation_service() -> RecommendationService:
    """Return the singleton RecommendationService instance."""
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                _service = RecommendationService()
    return _service
