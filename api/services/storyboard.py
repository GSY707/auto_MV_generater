"""
Storyboard 服务

使用 Gemini LLM 分析歌词和歌曲信息，生成 MV 分镜脚本。
每个场景对应一段固定时长的视频片段 (默认 8 秒)。

改进：
- 支持 highlight_start 偏移，可从任意位置开始选段
- 按歌词时间分配场景，避免歌词短/视频长的不匹配
- 只将相关歌词段落传给对应的场景
"""

import json
import math
from typing import Any, Dict, List, Optional

from src.clients.gemini import GeminiClient
from src.logger import get_logger

STORYBOARD_SYSTEM_PROMPT = """\
你是一位专业的 MV 导演和分镜师。你的任务是根据歌曲信息（标题、风格、歌词）创建详细的 MV 分镜脚本。

要求：
1. 严格按照每个场景的时间范围和对应歌词来设计画面
2. 每个场景的视觉描述要适合 AI 视频生成，包含：具体画面、光线、色调、镜头运动
3. 保持场景之间的视觉一致性（如主角外貌、色调风格）
4. 紧密结合每个场景对应的歌词内容和情绪变化
5. 使用电影和摄影术语（广角镜头、特写、推拉摇移等）
6. 如果某个场景没有对应歌词（间奏/前奏/尾奏），使用氛围画面填充

你必须输出严格的 JSON 数组，不要包含任何其他文本。

JSON 格式：
[
  {{
    "scene_index": 0,
    "start_time": 0.0,
    "end_time": 8.0,
    "description": "视频生成提示词（英文，2-3句，详细描述画面）",
    "mood": "场景情绪（如 dreamy, energetic, melancholic）",
    "lyrics_section": "对应的歌词片段（中文或原文）"
  }}
]

注意：
- description 必须用英文，因为视频生成模型对英文效果最好
- 描述要具体生动，避免抽象概念
- 每个 description 自成一体，不要引用"上一个场景"
- 如果歌词比视频短，后续无歌词的场景应设计纯视觉/氛围画面（如风景、抽象画面）
- 画面内容必须与对应时间段的歌词内容相匹配
"""

STORYBOARD_USER_PROMPT = """\
歌曲信息：
- 标题: {title}
- 风格标签: {tags}
- 视频起始时间: {start_time} 秒
- 视频总时长: {duration} 秒
- 每个场景时长: {scene_duration} 秒
- 所需场景数: {scene_count}

各场景的时间范围和对应歌词：
{scene_lyrics_mapping}

请为每个场景生成分镜脚本，画面必须匹配对应时间段的歌词内容。严格输出 JSON 数组。"""


def generate_storyboard(
    title: str,
    tags: str,
    lyrics: str,
    duration: float,
    scene_duration: int = 8,
    mode: str = "full",
    highlight_duration: int = 60,
    highlight_start: int = 0,
) -> List[Dict[str, Any]]:
    """生成 MV 分镜脚本

    Args:
        title: 歌曲标题
        tags: 风格标签
        lyrics: 歌词文本
        duration: 歌曲总时长 (秒)
        scene_duration: 每个场景的时长 (秒)
        mode: "full" (完整 MV) 或 "highlight" (精华片段)
        highlight_duration: highlight 模式的目标时长 (秒)
        highlight_start: highlight 模式的起始偏移 (秒)

    Returns:
        分镜脚本列表
    """
    logger = get_logger()

    if mode == "full":
        actual_start = 0
        actual_duration = duration
    else:
        actual_start = min(highlight_start, duration)
        actual_duration = min(highlight_duration, duration - actual_start)

    scene_count = math.ceil(actual_duration / scene_duration)
    scene_count = max(1, scene_count)

    logger.info(
        f"Storyboard: 生成分镜 (mode={mode}, start={actual_start}s, "
        f"duration={actual_duration}s, scenes={scene_count}, "
        f"scene_duration={scene_duration}s)"
    )

    # Build the scene-lyrics mapping for better time alignment
    scene_lyrics_mapping = _build_scene_lyrics_mapping(
        lyrics=lyrics,
        total_duration=duration,
        scene_start=actual_start,
        scene_duration=scene_duration,
        scene_count=scene_count,
    )

    system_prompt = STORYBOARD_SYSTEM_PROMPT.format(scene_duration=scene_duration)
    user_prompt = STORYBOARD_USER_PROMPT.format(
        title=title,
        tags=tags or "pop",
        start_time=actual_start,
        duration=actual_duration,
        scene_duration=scene_duration,
        scene_count=scene_count,
        scene_lyrics_mapping=scene_lyrics_mapping,
    )

    client = GeminiClient(timeout=120)
    content = client.chat(
        messages=[GeminiClient.make_user_message(user_prompt)],
        system_instruction=system_prompt,
    )
    text = GeminiClient.extract_text(content)

    # 解析 JSON（处理可能的 markdown 代码块包裹）
    scenes = _parse_storyboard_json(text)

    if not scenes:
        logger.warning("Storyboard: Gemini 返回的内容无法解析为场景列表，使用回退方案")
        scenes = _fallback_storyboard(
            title, tags, actual_start, actual_duration,
            scene_duration, scene_count, lyrics, duration,
        )

    # 确保时间轴正确（相对于歌曲开头的绝对时间）
    for i, scene in enumerate(scenes):
        scene["scene_index"] = i
        scene["start_time"] = actual_start + i * scene_duration
        scene["end_time"] = min(
            actual_start + (i + 1) * scene_duration,
            actual_start + actual_duration,
        )

    logger.info(f"Storyboard: 生成了 {len(scenes)} 个场景")
    return scenes


def _build_scene_lyrics_mapping(
    lyrics: str,
    total_duration: float,
    scene_start: float,
    scene_duration: int,
    scene_count: int,
) -> str:
    """Build a mapping of scene time ranges to corresponding lyrics sections.

    Distributes lyrics proportionally across the song duration, then extracts
    the portion relevant to each scene's time window. This ensures that scenes
    are matched to the correct lyrics even when highlight_start > 0.
    """
    if not lyrics or not lyrics.strip():
        lines_text = []
        for i in range(scene_count):
            s = scene_start + i * scene_duration
            e = min(s + scene_duration, scene_start + scene_count * scene_duration)
            lines_text.append(f"场景 {i+1} ({s:.0f}s ~ {e:.0f}s): (纯音乐，无歌词)")
        return "\n".join(lines_text)

    # Split lyrics into lines, filtering empties
    all_lines = [line for line in lyrics.split("\n") if line.strip()]

    if not all_lines:
        lines_text = []
        for i in range(scene_count):
            s = scene_start + i * scene_duration
            e = min(s + scene_duration, scene_start + scene_count * scene_duration)
            lines_text.append(f"场景 {i+1} ({s:.0f}s ~ {e:.0f}s): (纯音乐，无歌词)")
        return "\n".join(lines_text)

    # Estimate time per lyrics line (proportional to total song duration)
    # Assume lyrics cover roughly 80% of the song (leaving room for intro/outro)
    lyrics_start_ratio = 0.05  # lyrics typically start ~5% into the song
    lyrics_end_ratio = 0.95    # and end ~95%
    lyrics_time_start = total_duration * lyrics_start_ratio
    lyrics_time_end = total_duration * lyrics_end_ratio
    lyrics_span = lyrics_time_end - lyrics_time_start

    if lyrics_span <= 0:
        lyrics_span = total_duration
        lyrics_time_start = 0

    time_per_line = lyrics_span / len(all_lines)

    result_parts = []
    for i in range(scene_count):
        s = scene_start + i * scene_duration
        e = min(s + scene_duration, scene_start + scene_count * scene_duration)

        # Find which lyrics lines fall in this time range
        matched_lines = []
        for j, line in enumerate(all_lines):
            line_start = lyrics_time_start + j * time_per_line
            line_end = line_start + time_per_line
            # Check overlap
            if line_end > s and line_start < e:
                matched_lines.append(line.strip())

        if matched_lines:
            lyrics_text = " / ".join(matched_lines)
        else:
            # No lyrics for this section
            if s < lyrics_time_start:
                lyrics_text = "(前奏/间奏，无歌词)"
            elif s >= lyrics_time_end:
                lyrics_text = "(尾奏/fadeout，无歌词 - 请设计纯氛围画面)"
            else:
                lyrics_text = "(间奏，无歌词)"

        result_parts.append(f"场景 {i+1} ({s:.0f}s ~ {e:.0f}s): {lyrics_text}")

    return "\n".join(result_parts)


def _parse_storyboard_json(text: str) -> Optional[List[Dict[str, Any]]]:
    """尝试从 Gemini 输出中解析 JSON 数组"""
    # 去掉可能的 markdown 代码块
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        # 去掉首尾的 ``` 行
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    try:
        data = json.loads(text)
        if isinstance(data, list) and len(data) > 0:
            return data
    except json.JSONDecodeError:
        pass

    # 尝试找到 JSON 数组
    start = text.find("[")
    end = text.rfind("]")
    if start >= 0 and end > start:
        try:
            data = json.loads(text[start:end + 1])
            if isinstance(data, list):
                return data
        except json.JSONDecodeError:
            pass

    return None


def _fallback_storyboard(
    title: str,
    tags: str,
    start_offset: float,
    duration: float,
    scene_duration: int,
    scene_count: int,
    lyrics: str = "",
    total_duration: float = 0,
) -> List[Dict[str, Any]]:
    """回退方案：基于歌曲信息生成简单分镜，并尝试匹配歌词"""
    style = tags or "cinematic"
    scenes = []
    moods = ["establishing", "building", "emotional", "energetic", "climactic", "reflective"]

    # Split lyrics for assignment
    all_lines = [line.strip() for line in (lyrics or "").split("\n") if line.strip()]
    total_dur = total_duration or duration
    lyrics_time_start = total_dur * 0.05
    time_per_line = (total_dur * 0.9) / max(len(all_lines), 1) if all_lines else 0

    for i in range(scene_count):
        progress = i / max(scene_count - 1, 1)
        mood = moods[min(int(progress * len(moods)), len(moods) - 1)]

        s = start_offset + i * scene_duration
        e = min(s + scene_duration, start_offset + duration)

        # Find matching lyrics
        matched = []
        if all_lines and time_per_line > 0:
            for j, line in enumerate(all_lines):
                ls = lyrics_time_start + j * time_per_line
                le = ls + time_per_line
                if le > s and ls < e:
                    matched.append(line)

        lyrics_section = " / ".join(matched) if matched else ""

        desc_suffix = ""
        if not matched:
            desc_suffix = " Abstract atmospheric visuals, ambient mood."

        scenes.append({
            "scene_index": i,
            "start_time": s,
            "end_time": e,
            "description": (
                f"A {mood} cinematic scene for a {style} music video titled '{title}'. "
                f"Smooth camera movement, professional lighting, high quality visuals. "
                f"Scene {i + 1} of {scene_count}.{desc_suffix}"
            ),
            "mood": mood,
            "lyrics_section": lyrics_section,
        })
    return scenes
