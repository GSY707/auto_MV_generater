import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { useTasks } from '../context/TaskContext'
import { usePlayer } from '../context/PlayerContext'
import { TERMINAL_STATUSES } from '../utils/constants'
import { formatDateTime } from '../utils/formatDate'
import StatusBadge from '../components/Common/StatusBadge'
import LoadingSpinner from '../components/Common/LoadingSpinner'
import ClipList from '../components/Clip/ClipList'
import MVGenerateModal from '../components/MV/MVGenerateModal'
import styles from './TaskDetail.module.css'

export default function TaskDetail() {
  const { taskId } = useParams()
  const navigate = useNavigate()
  const { refreshTask } = useTasks()
  const { setPlaylist } = usePlayer()
  const [task, setTask] = useState(null)
  const [loading, setLoading] = useState(true)
  const [mvModalClip, setMvModalClip] = useState(null)
  const [mvTasks, setMvTasks] = useState([])
  const intervalRef = useRef(null)

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const data = await api.getTask(taskId)
        if (mounted) {
          setTask(data)
          setLoading(false)
          if (data.clips?.length > 0) setPlaylist(data.clips)
        }
      } catch {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => { mounted = false }
  }, [taskId, setPlaylist])

  // 加载关联的 MV 任务
  useEffect(() => {
    if (!task?.clips?.length) return
    const loadMVs = async () => {
      try {
        const allMvs = []
        for (const clip of task.clips) {
          const mvs = await api.getMVList(clip.id)
          allMvs.push(...mvs)
        }
        setMvTasks(allMvs)
      } catch { /* ignore */ }
    }
    loadMVs()
  }, [task?.clips])

  useEffect(() => {
    if (!task || TERMINAL_STATUSES.has(task.status)) {
      clearInterval(intervalRef.current)
      return
    }
    intervalRef.current = setInterval(async () => {
      try {
        const data = await api.getTask(taskId)
        setTask(data)
        refreshTask(taskId)
        if (data.clips?.length > 0) setPlaylist(data.clips)
      } catch { /* ignore */ }
    }, 3000)
    return () => clearInterval(intervalRef.current)
  }, [task?.status, taskId, refreshTask, setPlaylist])

  const handleMVSubmit = async (params) => {
    const result = await api.generateMV(params)
    setMvModalClip(null)
    navigate(`/mv/${result.mv_id}`)
  }

  if (loading) return <LoadingSpinner />
  if (!task) return <div style={{ color: 'var(--text-tertiary)', padding: 40 }}>任务不存在</div>

  const progress = task.progress ?? 0
  const isTerminal = TERMINAL_STATUSES.has(task.status)
  const isSuccess = task.status === 'SUCCESS'
  const lyrics = task.clips?.find(c => c.metadata?.prompt)?.metadata?.prompt

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <button className={styles.backBtn} onClick={() => navigate(-1)}>&larr;</button>
        <div className={styles.headerInfo}>
          <div className={styles.headerTitle}>
            {task.clips?.[0]?.title || task.params?.title || `任务 #${taskId.slice(0, 8)}`}
          </div>
          <div className={styles.headerMeta}>
            <StatusBadge status={task.status} />
            <span>{formatDateTime(task.created_at)}</span>
            {task.mode && <span>{task.mode === 'custom' ? '自定义模式' : '灵感模式'}</span>}
          </div>
        </div>
      </div>

      {!isTerminal && (
        <div className={styles.section}>
          <div className={styles.progressBar}>
            <div className={styles.progressFill} style={{ width: `${progress}%` }} />
          </div>
          <div className={styles.progressText}>{task.status} · {progress}%</div>
        </div>
      )}

      {task.clips?.length > 0 && (
        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>生成结果</h3>
          <ClipList clips={task.clips} />
        </div>
      )}

      {/* MV 生成按钮 */}
      {isSuccess && task.clips?.length > 0 && (
        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>MV 生成</h3>
          <div className={styles.mvClips}>
            {task.clips.map(clip => {
              const clipMvs = mvTasks.filter(m => m.clip_id === clip.id)
              return (
                <div key={clip.id} className={styles.mvClipRow}>
                  <div className={styles.mvClipInfo}>
                    <span className={styles.mvClipTitle}>{clip.title || 'Untitled'}</span>
                    {clipMvs.length > 0 && (
                      <div className={styles.mvExisting}>
                        {clipMvs.map(m => (
                          <button
                            key={m.mv_id}
                            className={styles.mvLink}
                            onClick={() => navigate(`/mv/${m.mv_id}`)}
                          >
                            MV · {m.status === 'SUCCESS' ? '已完成' : m.status === 'FAILURE' ? '失败' : '进行中'}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  <button
                    className={styles.mvGenerateBtn}
                    onClick={() => setMvModalClip(clip)}
                  >
                    生成 MV
                  </button>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {lyrics && (
        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>歌词</h3>
          <div className={styles.lyrics}>{lyrics}</div>
        </div>
      )}

      <div className={styles.section}>
        <h3 className={styles.sectionTitle}>详细信息</h3>
        <div className={styles.metaGrid}>
          <span className={styles.metaLabel}>任务 ID</span>
          <span className={styles.metaValue}>{task.task_id}</span>
          {task.params?.model && <>
            <span className={styles.metaLabel}>模型</span>
            <span className={styles.metaValue}>{task.params.model}</span>
          </>}
          {task.params?.tags && <>
            <span className={styles.metaLabel}>标签</span>
            <span className={styles.metaValue}>{task.params.tags}</span>
          </>}
          {task.finished_at && <>
            <span className={styles.metaLabel}>完成时间</span>
            <span className={styles.metaValue}>{formatDateTime(task.finished_at)}</span>
          </>}
        </div>
      </div>

      {task.saved && task.saved_files?.length > 0 && (
        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>已保存文件</h3>
          <div className={styles.savedFiles}>
            {task.saved_files.map(f => (
              <a key={f} className={styles.savedFile} href={`/api/output/${f}`} download>
                {f.endsWith('.mp3') ? '\u266A' : '\u{1F5BC}'} {f}
              </a>
            ))}
          </div>
        </div>
      )}

      {/* MV Modal */}
      {mvModalClip && (
        <MVGenerateModal
          clip={mvModalClip}
          taskId={taskId}
          onSubmit={handleMVSubmit}
          onClose={() => setMvModalClip(null)}
        />
      )}
    </div>
  )
}
