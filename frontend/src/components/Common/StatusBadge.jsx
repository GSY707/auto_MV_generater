import styles from './StatusBadge.module.css'

const STATUS_MAP = {
  NOT_START: { label: '未开始', style: 'pending' },
  SUBMITTED: { label: '已提交', style: 'active' },
  QUEUED: { label: '排队中', style: 'active' },
  IN_PROGRESS: { label: '生成中', style: 'active' },
  SUCCESS: { label: '已完成', style: 'success' },
  FAILURE: { label: '失败', style: 'error' },
  // MV statuses
  PENDING: { label: '等待中', style: 'pending' },
  GENERATING_STORYBOARD: { label: '生成分镜', style: 'active' },
  GENERATING_IMAGES: { label: '生成参考图', style: 'active' },
  GENERATING_VIDEO: { label: '生成视频', style: 'active' },
  STITCHING: { label: '拼接视频', style: 'active' },
}

export default function StatusBadge({ status, label }) {
  const info = STATUS_MAP[status] || { label: status, style: 'pending' }
  return (
    <span className={`${styles.badge} ${styles[info.style]}`}>
      <span className={styles.dot} />
      {label || info.label}
    </span>
  )
}
