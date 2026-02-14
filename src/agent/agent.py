"""
音乐生成 Agent 核心逻辑

基于 Gemini function calling 实现多步协调：
  用户输入 -> Gemini 推理 -> 工具调用 -> 结果反馈 -> 循环
"""

import json
from typing import Any, Dict, List, Optional

from ..clients.gemini import GeminiClient
from ..clients.suno import SunoClient
from ..tools.base import ToolManager
from ..tools.music import GenerateMusicTool, QueryTaskTool, WaitForTaskTool, GetWavTool
from ..config import get_config
from ..logger import get_logger
from .prompts import SYSTEM_PROMPT


class MusicAgent:
    """AI 音乐生成 Agent"""

    def __init__(
        self,
        gemini_client: Optional[GeminiClient] = None,
        suno_client: Optional[SunoClient] = None,
    ):
        self.cfg = get_config()
        self.logger = get_logger()
        self.gemini = gemini_client or GeminiClient()
        self.suno = suno_client or SunoClient()

        # 注册工具
        self.tool_manager = ToolManager()
        self.tool_manager.register(GenerateMusicTool(self.suno))
        self.tool_manager.register(QueryTaskTool(self.suno))
        self.tool_manager.register(WaitForTaskTool(self.suno))
        self.tool_manager.register(GetWavTool(self.suno))

        # 对话历史 (Gemini contents 格式)
        self.history: List[Dict[str, Any]] = []

    def reset(self):
        """清空对话历史"""
        self.history = []

    def run(self, user_input: str) -> str:
        """处理一次用户输入，返回最终文本回复

        内部会自动循环处理 function call 直到模型返回纯文本。
        """
        # 添加用户消息
        self.history.append(GeminiClient.make_user_message(user_input))
        self.logger.log_event("user_input", {"text": user_input[:500]})

        tools = self.tool_manager.get_gemini_tools()

        for step in range(1, self.cfg.max_agent_steps + 1):
            self.logger.info(f"Agent step {step}")

            # 调用 Gemini
            content = self.gemini.chat(
                messages=self.history,
                tools=tools,
                system_instruction=SYSTEM_PROMPT,
            )

            # 提取 function calls
            fn_calls = GeminiClient.extract_function_calls(content)
            text = GeminiClient.extract_text(content)

            if not fn_calls:
                # 没有工具调用 -> 最终回复
                self.history.append(GeminiClient.make_model_message(content))
                self.logger.log_event("agent_reply", {"step": step, "text": text[:500]})
                return text

            # 保存模型的 function call 消息
            self.history.append(GeminiClient.make_model_message(content))

            # 如果有文本输出，先打印
            if text:
                print(f"\n{text}")

            # 执行每个 function call 并反馈结果
            for fc in fn_calls:
                fn_name = fc["name"]
                fn_args = fc.get("args", {})

                self.logger.log_event("tool_call", {
                    "step": step,
                    "tool": fn_name,
                    "args": str(fn_args)[:300],
                })
                print(f"  [工具调用] {fn_name}({json.dumps(fn_args, ensure_ascii=False)[:200]})")

                result = self.tool_manager.execute(fn_name, **fn_args)

                self.logger.log_event("tool_result", {
                    "step": step,
                    "tool": fn_name,
                    "status": result.get("status"),
                    "result_preview": str(result.get("result", ""))[:300],
                })

                # 如果是 wait_for_task 且成功，打印进度
                if fn_name == "wait_for_task" and result.get("status") == "success":
                    print(f"  [完成] 任务已完成")
                elif result.get("status") == "error":
                    print(f"  [错误] {result.get('error', '未知错误')}")

                # 将工具结果反馈给 Gemini
                response_data = result.get("result") if result.get("status") == "success" else {"error": result.get("error")}
                self.history.append(
                    GeminiClient.make_function_response(fn_name, response_data)
                )

        # 超出最大步数
        self.logger.warning(f"Agent 超过最大步数 ({self.cfg.max_agent_steps})")
        return "抱歉，处理步骤过多，请简化您的需求后重试。"
