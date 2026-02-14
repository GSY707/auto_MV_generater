"""
启动时任务恢复

在服务器启动时自动检测并恢复中断的任务：
- 音乐任务 (Suno): 刷新非终态任务的状态
- MV 任务: 从断点恢复中断的 MV 生成流水线
"""

import threading

from src.logger import get_logger


def recover_interrupted_tasks():
    """在后台线程中恢复所有中断的任务。"""
    thread = threading.Thread(target=_do_recovery, daemon=True)
    thread.start()


def _do_recovery():
    logger = get_logger()
    logger.info("TaskRecovery: 开始检查中断的任务...")

    music_count = _recover_music_tasks(logger)
    mv_count = _recover_mv_tasks(logger)

    total = music_count + mv_count
    if total > 0:
        logger.info(f"TaskRecovery: 恢复了 {total} 个任务 (音乐: {music_count}, MV: {mv_count})")
    else:
        logger.info("TaskRecovery: 没有需要恢复的任务")


def _recover_music_tasks(logger) -> int:
    """刷新所有非终态的 Suno 音乐任务。"""
    try:
        from api.services.task_store import get_task_store
        from src.clients.suno import SunoClient

        store = get_task_store()
        active_ids = store.get_active_task_ids()

        if not active_ids:
            return 0

        logger.info(f"TaskRecovery: 发现 {len(active_ids)} 个活跃的音乐任务，开始刷新...")
        suno = SunoClient()
        recovered = 0

        for tid in active_ids:
            try:
                suno_data = suno.query_task(tid)
                record = store.update_from_suno_response(tid, suno_data)
                if record:
                    new_status = record.get("status", "")
                    logger.info(f"TaskRecovery: 音乐任务 {tid} 状态更新为 {new_status}")
                    recovered += 1
            except Exception as exc:
                logger.warning(f"TaskRecovery: 音乐任务 {tid} 刷新失败: {exc}")

        return recovered
    except Exception as exc:
        logger.error(f"TaskRecovery: 音乐任务恢复出错: {exc}")
        return 0


def _recover_mv_tasks(logger) -> int:
    """恢复所有中断的 MV 任务。"""
    try:
        from api.services.mv_store import get_mv_store, MV_RECOVERABLE, MV_STATUS_PENDING
        from api.services.mv_pipeline import resume_mv_pipeline

        store = get_mv_store()
        recoverable = store.get_recoverable_tasks()

        if not recoverable:
            return 0

        logger.info(f"TaskRecovery: 发现 {len(recoverable)} 个可恢复的 MV 任务")
        recovered = 0

        for rec in recoverable:
            mv_id = rec["mv_id"]
            status = rec.get("status")
            storyboard = rec.get("storyboard", [])
            tags = rec.get("tags", "")
            lyrics = rec.get("lyrics", "")

            # PENDING 状态且没有分镜也没有歌词/标签 → 无法恢复
            if status == MV_STATUS_PENDING and not storyboard and not tags and not lyrics:
                from api.services.mv_store import MV_STATUS_FAILURE
                store.update_status(mv_id, MV_STATUS_FAILURE, error="服务重启后无法恢复：缺少必要信息")
                logger.warning(f"TaskRecovery: MV 任务 {mv_id} 无法恢复（无分镜且无歌词），标记为失败")
                continue

            try:
                resume_mv_pipeline(mv_id)
                recovered += 1
                logger.info(f"TaskRecovery: MV 任务 {mv_id} (状态={status}) 已启动恢复")
            except Exception as exc:
                logger.error(f"TaskRecovery: MV 任务 {mv_id} 恢复启动失败: {exc}")

        return recovered
    except Exception as exc:
        logger.error(f"TaskRecovery: MV 任务恢复出错: {exc}")
        return 0
