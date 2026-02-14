"""
音乐生成 & 查询工具

封装 SunoClient 供 Agent 以 function calling 方式调用。
"""

from typing import Any, Dict, Optional

from .base import Tool
from ..clients.suno import SunoClient


class GenerateMusicTool(Tool):
    """提交音乐生成任务"""

    name = "generate_music"
    description = (
        "向 Suno 提交音乐生成任务。支持两种模式:\n"
        "1) 灵感模式(inspiration): 只需提供 description，AI 自动生成歌词和旋律\n"
        "2) 自定义模式(custom): 提供完整歌词(prompt)、标题(title)、风格标签(tags)\n"
        "返回 task_id，后续用 query_task 查询进度。"
    )

    def __init__(self, suno_client: SunoClient):
        self.suno = suno_client

    def get_function_declaration(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "mode": {
                        "type": "STRING",
                        "description": "生成模式: 'inspiration' 或 'custom'",
                        "enum": ["inspiration", "custom"],
                    },
                    "description": {
                        "type": "STRING",
                        "description": "灵感模式下的创作描述，例如 '一首关于春天的轻快民谣'",
                    },
                    "prompt": {
                        "type": "STRING",
                        "description": "自定义模式下的完整歌词（含段落标记如 [Verse]、[Chorus] 等）",
                    },
                    "title": {
                        "type": "STRING",
                        "description": "歌曲标题",
                    },
                    "tags": {
                        "type": "STRING",
                        "description": "风格标签，逗号分隔，如 'pop, electronic, upbeat'",
                    },
                    "make_instrumental": {
                        "type": "BOOLEAN",
                        "description": "是否生成纯音乐（无歌词演唱），默认 false",
                    },
                    "model": {
                        "type": "STRING",
                        "description": "Suno 模型版本: chirp-v3-5, chirp-v4, chirp-auk, chirp-v5。默认 chirp-v4",
                    },
                },
                "required": ["mode"],
            },
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        mode = kwargs.get("mode", "inspiration")
        make_instrumental = kwargs.get("make_instrumental", False)
        model = kwargs.get("model")

        try:
            if mode == "inspiration":
                desc = kwargs.get("description", "")
                if not desc:
                    return {"status": "error", "result": None, "error": "灵感模式需要 description 参数"}
                result = self.suno.generate_music_inspiration(
                    description=desc,
                    make_instrumental=make_instrumental,
                    mv=model,
                )
            else:
                prompt = kwargs.get("prompt", "")
                title = kwargs.get("title", "Untitled")
                tags = kwargs.get("tags", "")
                if not prompt and not make_instrumental:
                    return {"status": "error", "result": None, "error": "自定义模式需要 prompt(歌词) 参数"}
                result = self.suno.generate_music_custom(
                    prompt=prompt,
                    title=title,
                    tags=tags,
                    mv=model,
                    make_instrumental=make_instrumental,
                )

            if result.get("code") == "success":
                task_id = result.get("data", "")
                return {
                    "status": "success",
                    "result": {
                        "task_id": task_id,
                        "message": f"任务已提交，task_id={task_id}。请使用 query_task 查询进度。",
                    },
                    "error": None,
                }
            else:
                return {"status": "error", "result": result, "error": result.get("message", "提交失败")}

        except Exception as e:
            return {"status": "error", "result": None, "error": str(e)}


class QueryTaskTool(Tool):
    """查询任务状态"""

    name = "query_task"
    description = (
        "查询 Suno 音乐生成任务的状态。返回任务状态(NOT_START/SUBMITTED/QUEUED/IN_PROGRESS/SUCCESS/FAILURE)"
        "以及完成后的音乐数据(音频URL等)。"
    )

    def __init__(self, suno_client: SunoClient):
        self.suno = suno_client

    def get_function_declaration(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "task_id": {
                        "type": "STRING",
                        "description": "任务 ID",
                    },
                },
                "required": ["task_id"],
            },
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        task_id = kwargs.get("task_id", "")
        if not task_id:
            return {"status": "error", "result": None, "error": "需要 task_id 参数"}
        try:
            result = self.suno.query_task(task_id)
            return {"status": "success", "result": result, "error": None}
        except Exception as e:
            return {"status": "error", "result": None, "error": str(e)}


class WaitForTaskTool(Tool):
    """等待任务完成（带轮询）"""

    name = "wait_for_task"
    description = (
        "轮询等待 Suno 任务完成。会每隔一段时间自动查询状态，"
        "直到任务成功或失败。适用于用户希望一步到位获取结果时使用。"
    )

    def __init__(self, suno_client: SunoClient):
        self.suno = suno_client

    def get_function_declaration(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "task_id": {
                        "type": "STRING",
                        "description": "任务 ID",
                    },
                    "poll_interval": {
                        "type": "NUMBER",
                        "description": "轮询间隔秒数，默认 10",
                    },
                    "max_wait": {
                        "type": "NUMBER",
                        "description": "最大等待秒数，默认 600",
                    },
                },
                "required": ["task_id"],
            },
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        task_id = kwargs.get("task_id", "")
        if not task_id:
            return {"status": "error", "result": None, "error": "需要 task_id 参数"}
        poll_interval = kwargs.get("poll_interval", 10.0)
        max_wait = kwargs.get("max_wait", 600.0)
        try:
            result = self.suno.wait_for_task(task_id, poll_interval=poll_interval, max_wait=max_wait)
            code = result.get("code", "")
            if code == "timeout":
                return {"status": "error", "result": result, "error": "任务等待超时"}
            return {"status": "success", "result": result, "error": None}
        except Exception as e:
            return {"status": "error", "result": None, "error": str(e)}


class GetWavTool(Tool):
    """获取 WAV 音频信息"""

    name = "get_wav"
    description = "获取指定 clip 的 WAV 音频下载信息。"

    def __init__(self, suno_client: SunoClient):
        self.suno = suno_client

    def get_function_declaration(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "OBJECT",
                "properties": {
                    "clip_id": {
                        "type": "STRING",
                        "description": "歌曲 clip ID",
                    },
                },
                "required": ["clip_id"],
            },
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        clip_id = kwargs.get("clip_id", "")
        if not clip_id:
            return {"status": "error", "result": None, "error": "需要 clip_id 参数"}
        try:
            result = self.suno.get_wav_url(clip_id)
            return {"status": "success", "result": result, "error": None}
        except Exception as e:
            return {"status": "error", "result": None, "error": str(e)}
