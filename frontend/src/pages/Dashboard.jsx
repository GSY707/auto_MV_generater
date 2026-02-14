import { useNavigate } from 'react-router-dom'
import { useTasks } from '../context/TaskContext'
import { TERMINAL_STATUSES } from '../utils/constants'
import GlassCard from '../components/Common/GlassCard'
import LoadingSpinner from '../components/Common/LoadingSpinner'
import TaskGrid from '../components/Task/TaskGrid'
import styles from './Dashboard.module.css'

export default function Dashboard() {
  const { tasks, loading } = useTasks()
  const navigate = useNavigate()

  if (loading) return <LoadingSpinner />

  const active = tasks.filter(t => !TERMINAL_STATUSES.has(t.status))
  const completed = tasks.filter(t => t.status === 'SUCCESS')
  const failed = tasks.filter(t => t.status === 'FAILURE')

  return (
    <div className={styles.page}>
      <div className={styles.sectionHeader}>
        <h1 className="page-title">Dashboard</h1>
        <button className={styles.createBtn} onClick={() => navigate('/create')}>
          ＋ 创建新曲
        </button>
      </div>

      <div className={styles.stats}>
        <GlassCard hover={false}>
          <div className={`${styles.statNum} ${styles.statAccent}`}>{tasks.length}</div>
          <div className={styles.statLabel}>总任务</div>
        </GlassCard>
        <GlassCard hover={false}>
          <div className={`${styles.statNum} ${styles.statWarning}`}>{active.length}</div>
          <div className={styles.statLabel}>进行中</div>
        </GlassCard>
        <GlassCard hover={false}>
          <div className={`${styles.statNum} ${styles.statSuccess}`}>{completed.length}</div>
          <div className={styles.statLabel}>已完成</div>
        </GlassCard>
        <GlassCard hover={false}>
          <div className={`${styles.statNum} ${styles.statError}`}>{failed.length}</div>
          <div className={styles.statLabel}>失败</div>
        </GlassCard>
      </div>

      {active.length > 0 && (
        <div className={styles.section}>
          <div className={styles.sectionHeader}>
            <h2 className={styles.sectionTitle}>进行中</h2>
          </div>
          <TaskGrid tasks={active} />
        </div>
      )}

      <div className={styles.section}>
        <div className={styles.sectionHeader}>
          <h2 className={styles.sectionTitle}>最近完成</h2>
        </div>
        <TaskGrid tasks={completed.slice(0, 8)} />
      </div>
    </div>
  )
}
