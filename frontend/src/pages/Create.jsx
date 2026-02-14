import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { api } from '../api/client'
import { useTasks } from '../context/TaskContext'
import GlassCard from '../components/Common/GlassCard'
import InspirationForm from '../components/Create/InspirationForm'
import CustomForm from '../components/Create/CustomForm'
import styles from './Create.module.css'

export default function Create() {
  const location = useLocation()
  const suggestion = location.state?.suggestion
  const [mode, setMode] = useState(suggestion ? 'custom' : 'inspiration')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const navigate = useNavigate()
  const { addTask } = useTasks()

  const handleSubmit = async (params) => {
    setLoading(true)
    setError(null)
    try {
      const result = await api.generate(params)
      addTask(result)
      navigate(`/task/${result.task_id}`)
    } catch (err) {
      setError(err.message || '生成失败，请重试')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      <h1 className="page-title">创作新曲</h1>
      <div className={styles.tabs}>
        <button
          className={`${styles.tab} ${mode === 'inspiration' ? styles.active : ''}`}
          onClick={() => setMode('inspiration')}
        >
          灵感模式
        </button>
        <button
          className={`${styles.tab} ${mode === 'custom' ? styles.active : ''}`}
          onClick={() => setMode('custom')}
        >
          自定义模式
        </button>
      </div>
      <GlassCard hover={false} className={styles.formCard}>
        {mode === 'inspiration' ? (
          <InspirationForm onSubmit={handleSubmit} loading={loading} error={error} />
        ) : (
          <CustomForm onSubmit={handleSubmit} loading={loading} error={error} initialData={suggestion} />
        )}
      </GlassCard>
    </div>
  )
}
