"""
工具基类 & 工具管理器
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import logging

logger = logging.getLogger(__name__)


class Tool(ABC):
    """工具抽象基类"""

    name: str = ""
    description: str = ""

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """执行工具

        Returns:
            {"status": "success"|"error", "result": ..., "error": ...}
        """
        pass

    def get_function_declaration(self) -> Dict[str, Any]:
        """返回 Gemini function declaration 格式

        子类应覆写此方法以提供参数定义。
        """
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {"type": "OBJECT", "properties": {}, "required": []},
        }


class ToolManager:
    """管理工具注册与执行"""

    def __init__(self):
        self.tools: Dict[str, Tool] = {}

    def register(self, tool: Tool):
        self.tools[tool.name] = tool
        logger.info(f"工具已注册: {tool.name}")

    def execute(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        if tool_name not in self.tools:
            return {"status": "error", "result": None, "error": f"工具 '{tool_name}' 未找到"}
        try:
            return self.tools[tool_name].execute(**kwargs)
        except Exception as e:
            logger.error(f"工具 '{tool_name}' 执行异常: {e}")
            return {"status": "error", "result": None, "error": str(e)}

    def get_gemini_tools(self) -> List[Dict[str, Any]]:
        """返回所有工具的 Gemini function declarations（用于 API 请求）"""
        declarations = [t.get_function_declaration() for t in self.tools.values()]
        return [{"functionDeclarations": declarations}]

    def list_tools(self) -> List[str]:
        return list(self.tools.keys())
