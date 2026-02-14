"""
Development entry point for the Flask API server.

Run with:  python -m api.run
"""

import atexit
import signal
import socket
import sys
from pathlib import Path

# Ensure the project root is on sys.path so that 'src' and 'api' are importable
sys.path.insert(0, str(Path(__file__).parent.parent))


def _is_port_in_use(port: int) -> bool:
    """检测端口是否已被占用。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("127.0.0.1", port))
            return False
        except OSError:
            return True


def _graceful_shutdown():
    """优雅关闭：将活跃的 MV 任务标记为 INTERRUPTED。"""
    try:
        from api.services.mv_store import get_mv_store
        store = get_mv_store()
        count = store.mark_all_active_interrupted()
        if count > 0:
            print(f"\n[Shutdown] Marked {count} active MV tasks as INTERRUPTED")
    except Exception as exc:
        print(f"\n[Shutdown] Error during graceful shutdown: {exc}")


def _signal_handler(signum, frame):
    """处理 SIGINT/SIGTERM 信号。"""
    _graceful_shutdown()
    sys.exit(0)


if __name__ == "__main__":
    import os
    port = 5000

    # Flask debug reloader 会重新执行本模块，此时端口已被子进程占用，
    # 仅在首次启动时检测端口。
    is_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"

    if not is_reloader_child and _is_port_in_use(port):
        print(f"[ERROR] Port {port} is already in use.")
        print("        Another backend instance may be running.")
        print("        Run stop.bat to stop it, or use a different port.")
        sys.exit(1)

    # 标记 debug 模式，供 app.py 判断是否应触发任务恢复
    os.environ["FLASK_USE_RELOADER"] = "1"

    # 注册关闭钩子
    atexit.register(_graceful_shutdown)
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    from api.app import create_app
    app = create_app()
    app.run(host="127.0.0.1", port=port, debug=True)
