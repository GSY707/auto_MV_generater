import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { usePlayer } from '../../context/PlayerContext'
import { useTasks } from '../../context/TaskContext'
import GlassCard from '../Common/GlassCard'
import StatusBadge from '../Common/StatusBadge'
import { formatRelativeTime } from '../../utils/formatDate'
import styles from './TaskCard.module.css'

function getTaskTitle(task) {
  if (task.clips?.length > 0 && task.clips[0].title) return task.clips[0].title
  if (task.params?.title) return task.params.title
  if (task.params?.description) return task.params.description.slice(0, 30)
  return `任务 #${(task.task_id || '').slice(0, 6)}`
}

function getTaskImage(task) {
  if (task.clips?.length > 0 && task.clips[0].image_url) return task.clips[0].image_url
  return null
}

export default function TaskCard({ task }) {
  const navigate = useNavigate()
  const { play, setPlaylist } = usePlayer()
  const { deleteTask } = useTasks()
  const [confirming, setConfirming] = useState(false)
  const image = getTaskImage(task)
  const title = getTaskTitle(task)
  const isSuccess = task.status === 'SUCCESS'
  const hasClips = task.clips?.length > 0

  const handlePlay = (e) => {
    e.stopPropagation()
    if (hasClips) {
      setPlaylist(task.clips)
      play(task.clips[0])
    }
  }

  const handleDelete = (e) => {
    e.stopPropagation()
    if (!confirming) {
      setConfirming(true)
      setTimeout(() => setConfirming(false), 3000)
      return
    }
    deleteTask(task.task_id)
  }

  return (
    <GlassCard className={styles.card} onClick={() => navigate(`/task/${task.task_id}`)}>
      <div className={styles.artwork}>
        {image ? <img src={image} alt={title} /> : null}
        {isSuccess && hasClips && (
          <button className={styles.playOverlay} onClick={handlePlay}>▶</button>
        )}
        <button
          className={`${styles.deleteBtn} ${confirming ? styles.deleteBtnConfirm : ''}`}
          onClick={handleDelete}
          title={confirming ? '再次点击确认删除' : '删除任务'}
        >
          {confirming ? '确认?' : '×'}
        </button>
      </div>
      <div className={styles.info}>
        <div className={styles.titleRow}>
          <span className={styles.title}>{title}</span>
          <span className={styles.modeBadge}>
            {task.mode === 'custom' ? '自定义' : '灵感'}
          </span>
        </div>
        <div className={styles.meta}>
          <StatusBadge status={task.status} />
          <span className={styles.time}>{formatRelativeTime(task.created_at)}</span>
        </div>
        {task.params?.tags && (
          <div className={styles.tags}>{task.params.tags}</div>
        )}
      </div>
    </GlassCard>
  )
}
