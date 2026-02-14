import { useNavigate } from 'react-router-dom'
import TaskCard from './TaskCard'
import EmptyState from '../Common/EmptyState'
import styles from './TaskGrid.module.css'

export default function TaskGrid({ tasks }) {
  const navigate = useNavigate()

  if (!tasks || tasks.length === 0) {
    return (
      <EmptyState
        icon="♪"
        title="还没有任务"
        subtitle="创建你的第一首歌曲"
        actionLabel="开始创作"
        onAction={() => navigate('/create')}
      />
    )
  }

  return (
    <div className={styles.grid}>
      {tasks.map(t => <TaskCard key={t.task_id} task={t} />)}
    </div>
  )
}
