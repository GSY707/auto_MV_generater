"""
Blueprint: /api/mv

MV 生成相关的 API 端点。
"""

import re

from flask import Blueprint, jsonify, request, send_from_directory, send_file

from src.clients.suno import SunoClient
from src.clients.veo import VeoClient
from src.config import get_config
from src.logger import get_logger
from ..services.mv_store import get_mv_store, MV_TERMINAL
from ..services.mv_pipeline import start_mv_pipeline

mv_bp = Blueprint("mv", __name__)


@mv_bp.route("/mv/generate", methods=["POST"])
def mv_generate():
    """提交 MV 生成任务

    Request JSON::

        {
            "clip_id": "...",
            "task_id": "...",
            "mode": "full" | "highlight",
            "use_ref_images": false,
            "model": "veo-3.0-fast-generate-preview",
            "scene_duration": 8,
            "highlight_duration": 60
        }
    """
    logger = get_logger()
    body = request.get_json(force=True, silent=True) or {}
    cfg = get_config()

    clip_id = body.get("clip_id")
    task_id = body.get("task_id")
    if not clip_id:
        return jsonify({"error": "clip_id is required"}), 400

    mode = body.get("mode", "full")
    use_ref_images = bool(body.get("use_ref_images", False))
    model = body.get("model") or cfg.veo_model
    scene_duration = int(body.get("scene_duration", cfg.veo_scene_duration))
    highlight_duration = int(body.get("highlight_duration", 60))
    highlight_start = int(body.get("highlight_start", 0))

    # 验证 Vertex AI 凭据（Veo 必须使用 Vertex AI）
    if not cfg.vertex_ai_project_id:
        return jsonify({"error": "Veo 需要 Vertex AI 项目 ID (VERTEX_AI_PROJECT_ID)"}), 400

    # 获取 clip 信息
    clip_info = _get_clip_info(task_id, clip_id)
    if not clip_info:
        return jsonify({"error": f"找不到 clip: {clip_id}"}), 404

    title = clip_info.get("title", "Untitled")
    tags = clip_info.get("tags", "")
    lyrics = clip_info.get("lyrics", "")
    duration = clip_info.get("duration", 180)
    audio_url = clip_info.get("audio_url", "")

    # 创建 MV 任务
    store = get_mv_store()
    record = store.create(
        clip_id=clip_id,
        clip_title=title,
        mode=mode,
        use_ref_images=use_ref_images,
        model=model,
        scene_duration=scene_duration,
        audio_url=audio_url,
        duration=duration,
        tags=tags,
        lyrics=lyrics,
        highlight_duration=highlight_duration,
        highlight_start=highlight_start,
    )

    # 启动后台流水线
    start_mv_pipeline(
        mv_id=record["mv_id"],
        title=title,
        tags=tags,
        lyrics=lyrics,
        duration=duration,
        mode=mode,
        use_ref_images=use_ref_images,
        scene_duration=scene_duration,
        model=model,
        highlight_duration=highlight_duration,
        highlight_start=highlight_start,
    )

    logger.info(f"MV generate: started {record['mv_id']} for clip {clip_id}")
    return jsonify(record), 201


@mv_bp.route("/mv", methods=["GET"])
def mv_list():
    """列出所有 MV 任务"""
    store = get_mv_store()
    clip_id = request.args.get("clip_id")
    if clip_id:
        tasks = store.list_by_clip(clip_id)
    else:
        tasks = store.list_all()
    return jsonify(tasks)


@mv_bp.route("/mv/<mv_id>", methods=["GET"])
def mv_detail(mv_id):
    """查询单个 MV 任务详情"""
    store = get_mv_store()
    record = store.get(mv_id)
    if not record:
        return jsonify({"error": "MV task not found"}), 404
    return jsonify(record)


@mv_bp.route("/mv/<mv_id>", methods=["DELETE"])
def mv_delete(mv_id):
    """删除一个 MV 任务"""
    store = get_mv_store()
    if store.delete(mv_id):
        return jsonify({"ok": True})
    return jsonify({"error": "MV task not found"}), 404


@mv_bp.route("/mv/<mv_id>/scene/<int:scene_index>/video", methods=["GET"])
def mv_scene_video(mv_id, scene_index):
    """获取某个场景的视频文件"""
    store = get_mv_store()
    record = store.get(mv_id)
    if not record:
        return jsonify({"error": "MV task not found"}), 404

    scenes = record.get("scenes", [])
    if scene_index >= len(scenes):
        return jsonify({"error": "Scene not found"}), 404

    video_file = scenes[scene_index].get("video_file")
    if not video_file:
        return jsonify({"error": "Video not ready"}), 404

    mv_dir = store.get_mv_dir(mv_id)
    video_path = (mv_dir / video_file).resolve()
    if not video_path.exists():
        return jsonify({"error": "Video file not found"}), 404

    try:
        return send_file(
            video_path,
            mimetype="video/mp4",
            conditional=True,
        )
    except Exception as exc:
        get_logger().error(f"Scene video serve error [{mv_id}][{scene_index}]: {exc}")
        return jsonify({"error": "Failed to serve video"}), 500


@mv_bp.route("/mv/<mv_id>/scene/<int:scene_index>/image", methods=["GET"])
def mv_scene_image(mv_id, scene_index):
    """获取某个场景的参考图"""
    store = get_mv_store()
    record = store.get(mv_id)
    if not record:
        return jsonify({"error": "MV task not found"}), 404

    scenes = record.get("scenes", [])
    if scene_index >= len(scenes):
        return jsonify({"error": "Scene not found"}), 404

    image_file = scenes[scene_index].get("ref_image_file")
    if not image_file:
        return jsonify({"error": "Image not available"}), 404

    mv_dir = store.get_mv_dir(mv_id)
    return send_from_directory(str(mv_dir), image_file)


@mv_bp.route("/mv/<mv_id>/final", methods=["GET"])
def mv_final_video(mv_id):
    """获取最终拼接的 MV 视频"""
    store = get_mv_store()
    record = store.get(mv_id)
    if not record:
        return jsonify({"error": "MV task not found"}), 404

    video_path = record.get("video_path")
    if not video_path:
        return jsonify({"error": "Final video not available"}), 404

    cfg = get_config()
    full_path = (cfg.output_dir / video_path).resolve()
    if not full_path.exists():
        return jsonify({"error": "Video file not found"}), 404

    title = record.get("clip_title", "mv")
    # Sanitize title for safe filename (remove invalid characters)
    safe_title = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', title).strip()
    if not safe_title:
        safe_title = "mv"
    filename = f"{safe_title}_{mv_id[:8]}.mp4"

    try:
        return send_file(
            full_path,
            mimetype="video/mp4",
            as_attachment=True,
            download_name=filename,
            conditional=True,
        )
    except Exception as exc:
        get_logger().error(f"Final video serve error [{mv_id}]: {exc}")
        return jsonify({"error": "Failed to serve video"}), 500


@mv_bp.route("/mv/models", methods=["GET"])
def mv_models():
    """返回可用的 Veo 模型列表"""
    return jsonify({
        "models": VeoClient.SUPPORTED_MODELS,
        "default": get_config().veo_model,
    })


# ------------------------------------------------------------------ helpers

def _get_clip_info(task_id, clip_id):
    """从 TaskStore 或 Suno API 获取 clip 信息"""
    from ..services.task_store import get_task_store

    store = get_task_store()

    # 先从本地 task store 查找
    if task_id:
        task = store.get(task_id)
        if task:
            for clip in task.get("clips", []):
                if clip.get("id") == clip_id:
                    return {
                        "title": clip.get("title", "Untitled"),
                        "tags": clip.get("metadata", {}).get("tags", ""),
                        "lyrics": clip.get("metadata", {}).get("prompt", ""),
                        "duration": clip.get("metadata", {}).get("duration", 180),
                        "audio_url": clip.get("audio_url", ""),
                    }

    # 遍历所有任务查找
    for task in store.list_all():
        for clip in task.get("clips", []):
            if clip.get("id") == clip_id:
                return {
                    "title": clip.get("title", "Untitled"),
                    "tags": clip.get("metadata", {}).get("tags", ""),
                    "lyrics": clip.get("metadata", {}).get("prompt", ""),
                    "duration": clip.get("metadata", {}).get("duration", 180),
                    "audio_url": clip.get("audio_url", ""),
                }

    return None
