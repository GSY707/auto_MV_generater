import { useState, useEffect } from 'react'
import { api } from '../../api/client'
import ModelSelector from './ModelSelector'
import styles from './FormStyles.module.css'

export default function InspirationForm({ onSubmit, loading, error }) {
  const [description, setDescription] = useState('')
  const [model, setModel] = useState('chirp-v4')
  const [instrumental, setInstrumental] = useState(false)
  const [recommendations, setRecommendations] = useState([])

  useEffect(() => {
    api.getCreateRecommendations(4)
      .then(data => setRecommendations(data.recommendations || []))
      .catch(() => {})
  }, [])

  const handleRecommendationClick = async (rec) => {
    setDescription(rec)
    // Mark as clicked and refresh
    api.markRecommendationClicked(rec, 'create').catch(() => {})
    try {
      const data = await api.getCreateRecommendations(4)
      setRecommendations(data.recommendations || [])
    } catch {
      setRecommendations(prev => prev.filter(r => r !== rec))
    }
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!description.trim()) return
    onSubmit({
      mode: 'inspiration',
      description: description.trim(),
      model,
      instrumental,
    })
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <div className={styles.field}>
        <label>描述你想要的音乐</label>
        <textarea
          value={description}
          onChange={e => setDescription(e.target.value)}
          placeholder="例如：一首关于夏日海滩的轻快流行歌曲，带有吉他和轻柔的鼓点..."
        />
      </div>
      {recommendations.length > 0 && (
        <div className={styles.recommendations}>
          <label className={styles.recLabel}>试试这些灵感</label>
          <div className={styles.recChips}>
            {recommendations.map(rec => (
              <button
                key={rec}
                type="button"
                className={styles.recChip}
                onClick={() => handleRecommendationClick(rec)}
              >
                {rec}
              </button>
            ))}
          </div>
        </div>
      )}
      <div className={styles.row}>
        <div className={styles.field} style={{ flex: 1 }}>
          <label>模型</label>
          <ModelSelector value={model} onChange={setModel} />
        </div>
        <label className={styles.toggle}>
          <input
            type="checkbox"
            checked={instrumental}
            onChange={e => setInstrumental(e.target.checked)}
          />
          纯音乐（无人声）
        </label>
      </div>
      {error && <div className={styles.error}>{error}</div>}
      <button className={styles.submit} type="submit" disabled={loading || !description.trim()}>
        {loading ? '生成中...' : '开始生成'}
      </button>
    </form>
  )
}
