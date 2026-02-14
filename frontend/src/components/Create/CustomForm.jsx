import { useState } from 'react'
import ModelSelector from './ModelSelector'
import styles from './FormStyles.module.css'

export default function CustomForm({ onSubmit, loading, error, initialData }) {
  const [title, setTitle] = useState(initialData?.title || '')
  const [tags, setTags] = useState(initialData?.tags || '')
  const [prompt, setPrompt] = useState(initialData?.prompt || '')
  const [negativeTags, setNegativeTags] = useState('')
  const [model, setModel] = useState(initialData?.model || 'chirp-v4')
  const [instrumental, setInstrumental] = useState(false)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const handleSubmit = (e) => {
    e.preventDefault()
    if (!title.trim() || !prompt.trim()) return
    const params = {
      mode: 'custom',
      title: title.trim(),
      tags: tags.trim(),
      prompt: prompt.trim(),
      model,
      instrumental,
    }
    if (negativeTags.trim()) params.negative_tags = negativeTags.trim()
    onSubmit(params)
  }

  return (
    <form className={styles.form} onSubmit={handleSubmit}>
      <div className={styles.field}>
        <label>歌曲标题</label>
        <input
          type="text"
          value={title}
          onChange={e => setTitle(e.target.value)}
          placeholder="给你的歌曲起一个名字"
        />
      </div>
      <div className={styles.field}>
        <label>风格标签</label>
        <input
          type="text"
          value={tags}
          onChange={e => setTags(e.target.value)}
          placeholder="例如：pop, male vocals, upbeat, acoustic guitar"
        />
      </div>
      <div className={styles.field}>
        <label>歌词</label>
        <textarea
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          placeholder={"[Verse]\n在城市的夜空下\n灯火阑珊处等待\n\n[Chorus]\n让音乐带我飞翔\n穿越所有的梦想"}
          style={{ minHeight: 200 }}
        />
      </div>
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
          纯音乐
        </label>
      </div>

      <button
        type="button"
        className={styles.toggle}
        onClick={() => setShowAdvanced(!showAdvanced)}
        style={{ fontSize: 13 }}
      >
        {showAdvanced ? '▾ 收起高级选项' : '▸ 高级选项'}
      </button>
      {showAdvanced && (
        <div className={styles.field}>
          <label>排除标签（Negative Tags）</label>
          <input
            type="text"
            value={negativeTags}
            onChange={e => setNegativeTags(e.target.value)}
            placeholder="例如：auto-tune, electronic"
          />
        </div>
      )}

      {error && <div className={styles.error}>{error}</div>}
      <button className={styles.submit} type="submit" disabled={loading || !title.trim() || !prompt.trim()}>
        {loading ? '生成中...' : '开始生成'}
      </button>
    </form>
  )
}
