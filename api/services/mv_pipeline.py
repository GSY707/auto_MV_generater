"""
MV 生成流水线

编排：分镜生成 → 参考图生成 (可选) → Veo 视频生成 → ffmpeg 拼接
在后台线程中运行，通过 MVStore 实时更新状态。
"""

import base64
import re
import shutil
import subprocess
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.clients.veo import VeoClient
from src.clients.gemini import GeminiClient
from src.clients.gemini_image import GeminiImageClient
from src.logger import get_logger

from .mv_store import (
    MVStore,
    MV_STATUS_PENDING,
    MV_STATUS_STORYBOARD,
    MV_STATUS_IMAGES,
    MV_STATUS_VIDEO,
    MV_STATUS_STITCHING,
    MV_STATUS_SUCCESS,
    MV_STATUS_FAILURE,
    MV_STATUS_INTERRUPTED,
    get_mv_store,
)
from .storyboard import generate_storyboard

# 视频生成最大重试次数（包括提示词被拒后的重写重试）
MAX_SCENE_RETRIES = 3

# 匹配 Google Responsible AI 策略拒绝的错误
_PROMPT_REJECTED_PATTERN = re.compile(
    r"(sensitive words|Responsible AI|could not be submitted|violat)", re.IGNORECASE
)


def start_mv_pipeline(
    mv_id: str,
    title: str,
    tags: str,
    lyrics: str,
    duration: float,
    mode: str = "full",
    use_ref_images: bool = False,
    scene_duration: int = 8,
    model: Optional[str] = None,
    highlight_duration: int = 60,
    highlight_start: int = 0,
):
    """在后台线程中启动 MV 生成流水线"""
    thread = threading.Thread(
        target=_run_pipeline,
        args=(mv_id, title, tags, lyrics, duration, mode,
              use_ref_images, scene_duration, model, highlight_duration,
              highlight_start),
        daemon=True,
    )
    thread.start()


def _run_pipeline(
    mv_id: str,
    title: str,
    tags: str,
    lyrics: str,
    duration: float,
    mode: str,
    use_ref_images: bool,
    scene_duration: int,
    model: Optional[str],
    highlight_duration: int,
    highlight_start: int = 0,
):
    """MV 生成流水线主流程"""
    logger = get_logger()
    store = get_mv_store()
    mv_dir = store.get_mv_dir(mv_id)

    try:
        # ============================================================ 1. 分镜
        store.update_status(mv_id, MV_STATUS_STORYBOARD)
        logger.info(f"MV Pipeline [{mv_id}]: 开始生成分镜...")

        storyboard = generate_storyboard(
            title=title,
            tags=tags,
            lyrics=lyrics,
            duration=duration,
            scene_duration=scene_duration,
            mode=mode,
            highlight_duration=highlight_duration,
            highlight_start=highlight_start,
        )
        store.update_storyboard(mv_id, storyboard)
        logger.info(f"MV Pipeline [{mv_id}]: 分镜完成，共 {len(storyboard)} 个场景")

        # ============================================================ 2. 参考图 (可选)
        ref_images: Dict[int, tuple] = {}  # scene_index -> (base64, mime)

        if use_ref_images:
            store.update_status(mv_id, MV_STATUS_IMAGES)
            logger.info(f"MV Pipeline [{mv_id}]: 开始生成参考图...")

            img_client = GeminiImageClient()
            for scene in storyboard:
                idx = scene["scene_index"]
                prompt = (
                    f"Create a high-quality cinematic reference frame for a music video. "
                    f"Scene: {scene['description']}. "
                    f"Style: {tags or 'cinematic'}, photorealistic, 16:9 aspect ratio."
                )
                try:
                    result = img_client.generate_image_base64(prompt, aspect_ratio="16:9")
                    if result:
                        b64, mime = result
                        ref_images[idx] = (b64, mime)
                        # 保存参考图到磁盘
                        ext = "jpg" if "jpeg" in mime else "png"
                        img_path = mv_dir / f"ref_{idx:03d}.{ext}"
                        img_path.write_bytes(base64.b64decode(b64))
                        store.update_scene(mv_id, idx, {
                            "status": "image_done",
                            "ref_image_file": img_path.name,
                        })
                        logger.info(f"MV Pipeline [{mv_id}]: 参考图 {idx} 完成")
                except Exception as exc:
                    logger.warning(f"MV Pipeline [{mv_id}]: 参考图 {idx} 失败: {exc}")
                    store.update_scene(mv_id, idx, {"status": "image_failed"})

        # ============================================================ 3. Veo 视频生成
        store.update_status(mv_id, MV_STATUS_VIDEO)
        logger.info(f"MV Pipeline [{mv_id}]: 开始生成视频片段...")

        veo = VeoClient()

        # 提交所有场景
        operations: List[Dict[str, Any]] = []
        for scene in storyboard:
            idx = scene["scene_index"]
            desc = scene["description"]

            try:
                if idx in ref_images:
                    b64, mime = ref_images[idx]
                    op_name = veo.submit_image_to_video(
                        prompt=desc,
                        image_base64=b64,
                        image_mime=mime,
                        duration=scene_duration,
                        model=model,
                    )
                else:
                    op_name = veo.submit_text_to_video(
                        prompt=desc,
                        duration=scene_duration,
                        model=model,
                    )
                store.update_scene(mv_id, idx, {
                    "status": "submitted",
                    "operation_name": op_name,
                })
                op_entry = {
                    "scene_index": idx,
                    "operation_name": op_name,
                    "_desc": desc,
                    "_scene_duration": scene_duration,
                }
                if idx in ref_images:
                    op_entry["_ref_b64"] = ref_images[idx][0]
                    op_entry["_ref_mime"] = ref_images[idx][1]
                operations.append(op_entry)
                logger.info(f"MV Pipeline [{mv_id}]: 场景 {idx} 已提交")
            except Exception as exc:
                logger.error(f"MV Pipeline [{mv_id}]: 场景 {idx} 提交失败: {exc}")
                store.update_scene(mv_id, idx, {"status": "failed"})
                operations.append({"scene_index": idx, "operation_name": None, "_desc": desc})

            # 每次提交间隔 2 秒，避免速率限制
            if idx < len(storyboard) - 1:
                time.sleep(2)

        # 轮询所有操作直到完成
        _poll_all_operations(mv_id, operations, veo, store, mv_dir, model, logger)

        # ============================================================ 4. 拼接 (ffmpeg)
        store.update_status(mv_id, MV_STATUS_STITCHING)
        logger.info(f"MV Pipeline [{mv_id}]: 开始拼接视频...")

        # 收集所有场景视频（失败的场景使用占位视频）
        record = store.get(mv_id)
        scene_files = _collect_scene_files(
            record, storyboard, mv_dir, scene_duration, logger
        )

        if not scene_files:
            raise RuntimeError("没有成功生成任何视频片段")

        # 尝试用 ffmpeg 拼接，传入音频时长确保视频时长匹配
        audio_duration = duration
        final_path = _stitch_videos(
            mv_id, scene_files, mv_dir, record.get("audio_url"),
            logger, audio_duration=audio_duration,
        )

        if final_path:
            store.set_video_path(mv_id, str(final_path.relative_to(mv_dir.parent.parent)))
        else:
            # 没有 ffmpeg，只保留各个片段
            store.set_video_path(mv_id, None)

        store.update_status(mv_id, MV_STATUS_SUCCESS)
        logger.info(f"MV Pipeline [{mv_id}]: MV 生成完成!")

    except Exception as exc:
        logger.error(f"MV Pipeline [{mv_id}]: 流水线失败: {exc}")
        store.update_status(mv_id, MV_STATUS_FAILURE, error=str(exc))


def _rewrite_prompt_for_safety(original_prompt: str, logger) -> Optional[str]:
    """使用 Gemini 重写被 Google Responsible AI 策略拒绝的视频提示词

    Returns:
        重写后的提示词，或 None（如果重写失败）
    """
    try:
        gemini = GeminiClient()
        system_instruction = (
            "You are a prompt rewriter for a video generation AI. "
            "The original prompt was rejected by Google's Responsible AI policy "
            "for containing sensitive words. "
            "Rewrite the prompt to convey the same visual scene and mood, "
            "but remove or rephrase any potentially sensitive content "
            "(violence, gore, explicit content, controversial topics, etc.). "
            "Keep the cinematic quality and visual description. "
            "Output ONLY the rewritten prompt, nothing else."
        )
        messages = [
            GeminiClient.make_user_message(
                f"Rewrite this video generation prompt to comply with safety policies:\n\n{original_prompt}"
            )
        ]
        content = gemini.chat(
            messages=messages, system_instruction=system_instruction
        )
        rewritten = GeminiClient.extract_text(content).strip()
        if rewritten:
            logger.info(f"Prompt rewritten: '{original_prompt[:60]}...' -> '{rewritten[:60]}...'")
            return rewritten
    except Exception as exc:
        logger.warning(f"Prompt rewrite failed: {exc}")
    return None


def _poll_all_operations(
    mv_id: str,
    operations: List[Dict[str, Any]],
    veo: VeoClient,
    store: MVStore,
    mv_dir: Path,
    model: Optional[str],
    logger,
):
    """轮询所有 Veo 操作直到完成或超时"""
    pending = [op for op in operations if op["operation_name"] is not None]
    max_wait = 900  # 15 分钟总超时
    poll_interval = 15
    elapsed = 0

    retry_queue = []  # 需要重试的场景 (空视频或提示词被拒)

    while pending and elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval

        still_pending = []
        for op in pending:
            idx = op["scene_index"]
            op_name = op["operation_name"]
            retried = op.get("_retried", 0)
            try:
                done, result = veo.poll_operation(op_name, model)
                if done:
                    # 保存视频
                    video_path = mv_dir / f"scene_{idx:03d}.mp4"
                    saved = VeoClient.save_video_from_response(result, video_path)
                    if saved:
                        store.update_scene(mv_id, idx, {
                            "status": "done",
                            "video_file": saved.name,
                        })
                        logger.info(f"MV Pipeline [{mv_id}]: 场景 {idx} 视频完成")
                    else:
                        # 空视频 (可能被内容过滤)，加入重试队列
                        if retried < MAX_SCENE_RETRIES:
                            logger.warning(
                                f"MV Pipeline [{mv_id}]: 场景 {idx} 视频为空 "
                                f"(重试 {retried}/{MAX_SCENE_RETRIES})，将重试"
                            )
                            op["_needs_rewrite"] = True
                            retry_queue.append(op)
                        else:
                            store.update_scene(mv_id, idx, {"status": "failed"})
                            logger.warning(
                                f"MV Pipeline [{mv_id}]: 场景 {idx} 达到最大重试次数 "
                                f"({MAX_SCENE_RETRIES})，标记失败"
                            )
                else:
                    still_pending.append(op)
            except Exception as exc:
                exc_str = str(exc)
                # 检测是否为提示词被 Responsible AI 策略拒绝
                if _PROMPT_REJECTED_PATTERN.search(exc_str):
                    if retried < MAX_SCENE_RETRIES:
                        logger.warning(
                            f"MV Pipeline [{mv_id}]: 场景 {idx} 提示词被拒 "
                            f"(重试 {retried}/{MAX_SCENE_RETRIES})，将重写提示词后重试"
                        )
                        op["_needs_rewrite"] = True
                        retry_queue.append(op)
                    else:
                        store.update_scene(mv_id, idx, {"status": "failed"})
                        logger.error(
                            f"MV Pipeline [{mv_id}]: 场景 {idx} 提示词多次被拒 "
                            f"({MAX_SCENE_RETRIES} 次)，标记失败: {exc_str}"
                        )
                else:
                    logger.warning(f"MV Pipeline [{mv_id}]: 场景 {idx} 轮询错误: {exc}")
                    still_pending.append(op)

        pending = still_pending

        # 处理重试队列: 重写提示词 (如需要) 并重新提交
        if retry_queue and not pending:
            for op in retry_queue:
                idx = op["scene_index"]
                op_retried = op.get("_retried", 0)
                try:
                    scene_desc = op.get("_desc", "")
                    ref_b64 = op.get("_ref_b64")
                    ref_mime = op.get("_ref_mime")
                    sd = op.get("_scene_duration", 8)

                    # 如果需要重写提示词 (被 Responsible AI 拒绝或内容过滤)
                    if op.get("_needs_rewrite"):
                        rewritten = _rewrite_prompt_for_safety(scene_desc, logger)
                        if rewritten:
                            scene_desc = rewritten
                            op["_desc"] = rewritten
                        op.pop("_needs_rewrite", None)

                    if ref_b64:
                        new_op_name = veo.submit_image_to_video(
                            prompt=scene_desc, image_base64=ref_b64,
                            image_mime=ref_mime, duration=sd, model=model,
                        )
                    else:
                        new_op_name = veo.submit_text_to_video(
                            prompt=scene_desc, duration=sd, model=model,
                        )
                    store.update_scene(mv_id, idx, {
                        "status": "retrying",
                        "operation_name": new_op_name,
                    })
                    pending.append({
                        "scene_index": idx, "operation_name": new_op_name,
                        "_retried": op_retried + 1,
                        **{k: v for k, v in op.items()
                           if k.startswith("_") and k != "_retried"},
                    })
                    logger.info(
                        f"MV Pipeline [{mv_id}]: 场景 {idx} 已重新提交 "
                        f"(第 {op_retried + 1} 次重试)"
                    )
                    time.sleep(2)
                except Exception as exc:
                    store.update_scene(mv_id, idx, {"status": "failed"})
                    logger.error(f"MV Pipeline [{mv_id}]: 场景 {idx} 重试提交失败: {exc}")
            retry_queue.clear()

        logger.info(
            f"MV Pipeline [{mv_id}]: 视频进度 - "
            f"{len(operations) - len(pending)}/{len(operations)} 完成 "
            f"(已等待 {elapsed}s)"
        )

    # 标记超时的场景为失败
    for op in pending:
        store.update_scene(mv_id, op["scene_index"], {"status": "timeout"})


def _create_placeholder_video(
    scene_index: int,
    duration: float,
    mv_dir: Path,
    ref_image_file: Optional[str],
    logger,
) -> Optional[Path]:
    """为失败的场景创建占位视频（使用参考图或黑屏）

    Args:
        scene_index: 场景索引
        duration: 视频时长（秒）
        mv_dir: MV 输出目录
        ref_image_file: 参考图文件名（可选）
        logger: 日志实例

    Returns:
        生成的占位视频路径，或 None（ffmpeg 不可用时）
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return None

    output_path = mv_dir / f"scene_{scene_index:03d}.mp4"

    # 优先使用参考图，否则生成黑屏
    if ref_image_file:
        img_path = mv_dir / ref_image_file
        if img_path.exists():
            # 将静态图片转为指定时长的视频
            cmd = [
                ffmpeg, "-y",
                "-loop", "1",
                "-i", str(img_path),
                "-c:v", "libx264",
                "-t", str(duration),
                "-pix_fmt", "yuv420p",
                "-vf", "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2",
                "-r", "24",
                str(output_path),
            ]
        else:
            ref_image_file = None  # 文件不存在，回退到黑屏

    if not ref_image_file:
        # 生成黑屏视频
        cmd = [
            ffmpeg, "-y",
            "-f", "lavfi",
            "-i", f"color=c=black:s=1920x1080:d={duration}:r=24",
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            str(output_path),
        ]

    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=60)
        logger.info(
            f"MV Pipeline: 场景 {scene_index} 使用"
            f"{'参考图' if ref_image_file else '黑屏'}占位视频 ({duration}s)"
        )
        return output_path
    except Exception as exc:
        logger.error(f"MV Pipeline: 场景 {scene_index} 占位视频生成失败: {exc}")
        return None


def _collect_scene_files(
    record: Dict[str, Any],
    storyboard: List[Dict[str, Any]],
    mv_dir: Path,
    scene_duration: int,
    logger,
) -> List[Path]:
    """收集所有场景的视频文件，对失败的场景生成占位视频

    Returns:
        按场景顺序排列的视频文件路径列表
    """
    scenes = record.get("scenes", [])
    scene_files = []

    for scene in storyboard:
        idx = scene["scene_index"]
        scene_state = scenes[idx] if idx < len(scenes) else {}
        vf = scene_state.get("video_file")

        if vf:
            full_path = mv_dir / vf
            if full_path.exists():
                scene_files.append(full_path)
                continue

        # 视频不存在或生成失败 → 创建占位视频
        expected_dur = scene.get("end_time", 0) - scene.get("start_time", 0)
        if expected_dur <= 0:
            expected_dur = scene_duration

        ref_image = scene_state.get("ref_image_file")
        placeholder = _create_placeholder_video(
            idx, expected_dur, mv_dir, ref_image, logger
        )
        if placeholder:
            scene_files.append(placeholder)

    return scene_files


def _stitch_videos(
    mv_id: str,
    scene_files: List[Path],
    mv_dir: Path,
    audio_url: Optional[str],
    logger,
    audio_duration: float = 0,
) -> Optional[Path]:
    """使用 ffmpeg 拼接视频片段，可选叠加音频，确保视频时长等于音频时长

    Args:
        mv_id: MV 任务 ID
        scene_files: 场景视频文件列表
        mv_dir: MV 输出目录
        audio_url: 音频文件路径或 URL
        logger: 日志实例
        audio_duration: 目标音频时长（秒），用于确保最终视频时长匹配
    """
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        logger.warning(f"MV Pipeline [{mv_id}]: ffmpeg 未安装，跳过拼接")
        return None

    # 1. 创建 concat 文件列表
    concat_list = mv_dir / "concat.txt"
    with open(concat_list, "w", encoding="utf-8") as f:
        for sf in sorted(scene_files):
            f.write(f"file '{sf.name}'\n")

    # 2. 拼接视频 (无音频)
    concat_out = mv_dir / "concat_noaudio.mp4"
    cmd = [
        ffmpeg, "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list),
        "-c", "copy",
        str(concat_out),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, timeout=120)
    except Exception as exc:
        logger.error(f"MV Pipeline [{mv_id}]: ffmpeg concat 失败: {exc}")
        return None

    # 3. 叠加音频 (如果有)，并确保最终视频时长等于音频时长
    if audio_url:
        final_out = mv_dir / "final.mp4"
        cmd = [
            ffmpeg, "-y",
            "-i", str(concat_out),
            "-i", audio_url,
            "-c:v", "libx264",
            "-c:a", "aac",
        ]
        # 使用音频时长作为目标时长，确保视频与音频等长
        if audio_duration > 0:
            cmd.extend(["-t", str(audio_duration)])
        else:
            cmd.append("-shortest")
        cmd.append(str(final_out))
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=300)
            logger.info(f"MV Pipeline [{mv_id}]: 最终视频已生成 (含音频)")
            return final_out
        except Exception as exc:
            logger.warning(f"MV Pipeline [{mv_id}]: 音频叠加失败: {exc}，返回无音频版本")
            return concat_out
    else:
        return concat_out


def resume_mv_pipeline(mv_id: str):
    """恢复一个中断的 MV 生成任务，从断点继续执行。"""
    thread = threading.Thread(
        target=_resume_pipeline,
        args=(mv_id,),
        daemon=True,
    )
    thread.start()


def _resume_pipeline(mv_id: str):
    """根据 MV 当前状态从断点继续执行。"""
    logger = get_logger()
    store = get_mv_store()
    record = store.get(mv_id)

    if not record:
        logger.error(f"MV Resume [{mv_id}]: 找不到任务记录")
        return

    status = record.get("status")
    storyboard = record.get("storyboard", [])
    scenes = record.get("scenes", [])
    mv_dir = store.get_mv_dir(mv_id)

    # 从 record 读取恢复所需的参数
    title = record.get("clip_title", "Untitled")
    tags = record.get("tags", "")
    lyrics = record.get("lyrics", "")
    duration = record.get("duration", 180)
    mode = record.get("mode", "full")
    use_ref_images = record.get("use_ref_images", False)
    scene_duration = record.get("scene_duration", 8)
    model = record.get("model")
    highlight_duration = record.get("highlight_duration", 60)
    highlight_start = record.get("highlight_start", 0)

    logger.info(f"MV Resume [{mv_id}]: 恢复任务，当前状态={status}")

    try:
        # 无分镜数据 → 需要重新生成（需要 title/tags/lyrics）
        if not storyboard:
            if not tags and not lyrics:
                raise RuntimeError("无法恢复：缺少歌词/标签信息，且分镜尚未生成")
            logger.info(f"MV Resume [{mv_id}]: 无分镜数据，从头开始")
            _run_pipeline(
                mv_id, title, tags, lyrics, duration, mode,
                use_ref_images, scene_duration, model,
                highlight_duration, highlight_start,
            )
            return

        # 有分镜数据 → 判断从哪个步骤继续
        all_videos_done = all(
            s.get("video_file") for s in scenes
        ) if scenes else False

        # 所有视频都完成了 → 直接拼接
        if all_videos_done:
            logger.info(f"MV Resume [{mv_id}]: 所有视频已完成，直接拼接")
            _resume_stitch(mv_id, store, mv_dir, record, logger)
            return

        # 需要生成/恢复参考图
        ref_images: Dict[int, tuple] = {}
        if use_ref_images:
            needs_images = False
            for scene_state in scenes:
                idx = scene_state.get("scene_index", 0)
                ref_file = scene_state.get("ref_image_file")
                if ref_file:
                    ref_path = mv_dir / ref_file
                    if ref_path.exists():
                        b64 = base64.b64encode(ref_path.read_bytes()).decode()
                        mime = "image/png" if ref_file.endswith(".png") else "image/jpeg"
                        ref_images[idx] = (b64, mime)
                elif scene_state.get("status") not in ("image_done", "done", "submitted", "retrying"):
                    needs_images = True

            if needs_images:
                store.update_status(mv_id, MV_STATUS_IMAGES)
                logger.info(f"MV Resume [{mv_id}]: 继续生成剩余参考图...")
                img_client = GeminiImageClient()
                for scene in storyboard:
                    idx = scene["scene_index"]
                    if idx in ref_images:
                        continue
                    scene_state = scenes[idx] if idx < len(scenes) else {}
                    if scene_state.get("ref_image_file"):
                        continue
                    prompt = (
                        f"Create a high-quality cinematic reference frame for a music video. "
                        f"Scene: {scene['description']}. "
                        f"Style: {tags or 'cinematic'}, photorealistic, 16:9 aspect ratio."
                    )
                    try:
                        result = img_client.generate_image_base64(prompt, aspect_ratio="16:9")
                        if result:
                            b64, mime = result
                            ref_images[idx] = (b64, mime)
                            ext = "jpg" if "jpeg" in mime else "png"
                            img_path = mv_dir / f"ref_{idx:03d}.{ext}"
                            img_path.write_bytes(base64.b64decode(b64))
                            store.update_scene(mv_id, idx, {
                                "status": "image_done",
                                "ref_image_file": img_path.name,
                            })
                            logger.info(f"MV Resume [{mv_id}]: 参考图 {idx} 完成")
                    except Exception as exc:
                        logger.warning(f"MV Resume [{mv_id}]: 参考图 {idx} 失败: {exc}")
                        store.update_scene(mv_id, idx, {"status": "image_failed"})

        # 生成/恢复视频
        store.update_status(mv_id, MV_STATUS_VIDEO)
        logger.info(f"MV Resume [{mv_id}]: 继续生成视频片段...")

        veo = VeoClient()
        operations: List[Dict[str, Any]] = []

        for scene in storyboard:
            idx = scene["scene_index"]
            scene_state = scenes[idx] if idx < len(scenes) else {}
            desc = scene["description"]

            # 已有完成的视频文件 → 跳过
            if scene_state.get("video_file"):
                video_path = mv_dir / scene_state["video_file"]
                if video_path.exists():
                    logger.info(f"MV Resume [{mv_id}]: 场景 {idx} 视频已存在，跳过")
                    continue

            # 已有 operation_name → 加入轮询队列
            if scene_state.get("operation_name"):
                op_entry = {
                    "scene_index": idx,
                    "operation_name": scene_state["operation_name"],
                    "_desc": desc,
                    "_scene_duration": scene_duration,
                }
                if idx in ref_images:
                    op_entry["_ref_b64"] = ref_images[idx][0]
                    op_entry["_ref_mime"] = ref_images[idx][1]
                operations.append(op_entry)
                logger.info(f"MV Resume [{mv_id}]: 场景 {idx} 恢复轮询 operation")
                continue

            # 没有视频也没有 operation → 重新提交
            try:
                if idx in ref_images:
                    b64, mime = ref_images[idx]
                    op_name = veo.submit_image_to_video(
                        prompt=desc, image_base64=b64, image_mime=mime,
                        duration=scene_duration, model=model,
                    )
                else:
                    op_name = veo.submit_text_to_video(
                        prompt=desc, duration=scene_duration, model=model,
                    )
                store.update_scene(mv_id, idx, {
                    "status": "submitted",
                    "operation_name": op_name,
                })
                op_entry = {
                    "scene_index": idx,
                    "operation_name": op_name,
                    "_desc": desc,
                    "_scene_duration": scene_duration,
                }
                if idx in ref_images:
                    op_entry["_ref_b64"] = ref_images[idx][0]
                    op_entry["_ref_mime"] = ref_images[idx][1]
                operations.append(op_entry)
                logger.info(f"MV Resume [{mv_id}]: 场景 {idx} 重新提交")
            except Exception as exc:
                logger.error(f"MV Resume [{mv_id}]: 场景 {idx} 提交失败: {exc}")
                store.update_scene(mv_id, idx, {"status": "failed"})

            time.sleep(2)

        # 轮询
        if operations:
            _poll_all_operations(mv_id, operations, veo, store, mv_dir, model, logger)

        # 拼接
        _resume_stitch(mv_id, store, mv_dir, store.get(mv_id), logger)

    except Exception as exc:
        logger.error(f"MV Resume [{mv_id}]: 恢复失败: {exc}")
        store.update_status(mv_id, MV_STATUS_FAILURE, error=str(exc))


def _resume_stitch(mv_id, store, mv_dir, record, logger):
    """拼接阶段（恢复用）"""
    store.update_status(mv_id, MV_STATUS_STITCHING)
    logger.info(f"MV Resume [{mv_id}]: 开始拼接视频...")

    storyboard = record.get("storyboard", [])
    scene_duration = record.get("scene_duration", 8)
    audio_duration = record.get("duration", 0)

    scene_files = _collect_scene_files(
        record, storyboard, mv_dir, scene_duration, logger
    )

    if not scene_files:
        raise RuntimeError("没有成功生成任何视频片段")

    final_path = _stitch_videos(
        mv_id, scene_files, mv_dir, record.get("audio_url"),
        logger, audio_duration=audio_duration,
    )

    if final_path:
        store.set_video_path(mv_id, str(final_path.relative_to(mv_dir.parent.parent)))
    else:
        store.set_video_path(mv_id, None)

    store.update_status(mv_id, MV_STATUS_SUCCESS)
    logger.info(f"MV Resume [{mv_id}]: MV 恢复生成完成!")

