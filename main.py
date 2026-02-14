"""
AI 音乐生成 Agent - 主入口

用法:
    python main.py                  # 交互式对话模式
    python main.py --once "描述"    # 单次生成模式
"""

import sys
import argparse

from src.config import get_config
from src.agent.agent import MusicAgent


def print_banner():
    print("=" * 56)
    print("  AI Music Agent  |  Gemini + Suno")
    print("=" * 56)
    print("  输入你的音乐创作需求，Agent 会帮你生成音乐。")
    print("  命令:  /reset  清空对话  |  /quit  退出")
    print("=" * 56)
    print()


def interactive_mode():
    """交互式对话模式"""
    cfg = get_config()
    if not cfg.validate():
        print("配置验证失败，请检查 .env 文件。")
        sys.exit(1)

    print_banner()
    print(f"  后端: {cfg.gemini_backend}  |  模型: {cfg.gemini_model}")
    print(f"  Suno: {cfg.suno_base_url}  |  Suno模型: {cfg.suno_model}")
    print()

    agent = MusicAgent()

    while True:
        try:
            user_input = input("你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见!")
            break

        if not user_input:
            continue

        if user_input.lower() in ("/quit", "/exit", "quit", "exit"):
            print("再见!")
            break

        if user_input.lower() == "/reset":
            agent.reset()
            print("[对话已重置]\n")
            continue

        try:
            reply = agent.run(user_input)
            print(f"\nAgent: {reply}\n")
        except KeyboardInterrupt:
            print("\n[已中断]")
        except Exception as e:
            print(f"\n[错误] {e}\n")


def single_mode(prompt: str):
    """单次生成模式"""
    cfg = get_config()
    if not cfg.validate():
        print("配置验证失败，请检查 .env 文件。")
        sys.exit(1)

    agent = MusicAgent()
    try:
        reply = agent.run(prompt)
        print(f"\n{reply}")
    except Exception as e:
        print(f"[错误] {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="AI Music Agent")
    parser.add_argument("--once", type=str, default=None, help="单次生成模式，传入创作描述")
    args = parser.parse_args()

    if args.once:
        single_mode(args.once)
    else:
        interactive_mode()


if __name__ == "__main__":
    main()
