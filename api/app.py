"""
Flask application factory.

Creates and configures the Flask app with CORS and all route blueprints.
"""

from flask import Flask, jsonify
from flask_cors import CORS

from src.config import get_config


def create_app() -> Flask:
    """Create and configure the Flask application.

    Returns:
        A fully configured Flask app instance.
    """
    get_config()  # ensure .env is loaded

    app = Flask(__name__)
    CORS(app, origins=["http://localhost:5173"])

    from .routes.generate import generate_bp
    from .routes.tasks import tasks_bp
    from .routes.chat import chat_bp
    from .routes.files import files_bp
    from .routes.mv import mv_bp
    from .routes.recommendations import recommendations_bp
    from .routes.chat_history import chat_history_bp

    app.register_blueprint(generate_bp, url_prefix="/api")
    app.register_blueprint(tasks_bp, url_prefix="/api")
    app.register_blueprint(chat_bp, url_prefix="/api")
    app.register_blueprint(files_bp, url_prefix="/api")
    app.register_blueprint(mv_bp, url_prefix="/api")
    app.register_blueprint(recommendations_bp, url_prefix="/api")
    app.register_blueprint(chat_history_bp, url_prefix="/api")

    # Ensure API routes always return JSON, never HTML error pages
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(500)
    def internal_error(e):
        return jsonify({"error": "Internal server error"}), 500

    # 启动时恢复中断的任务
    # debug 模式下 Flask reloader 会创建父子两个进程，仅在子进程中恢复。
    # 非 debug 模式下（无 reloader），直接恢复。
    import os
    use_reloader = os.environ.get("FLASK_USE_RELOADER") == "1"
    is_reloader_child = os.environ.get("WERKZEUG_RUN_MAIN") == "true"
    if is_reloader_child or not use_reloader:
        from .services.task_recovery import recover_interrupted_tasks
        recover_interrupted_tasks()

    return app
