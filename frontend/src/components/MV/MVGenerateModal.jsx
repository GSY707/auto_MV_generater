import { useState } from 'react'
import { VEO_MODELS } from '../../utils/constants'
import styles from './MVGenerateModal.module.css'

export default function MVGenerateModal({ clip, taskId, onSubmit, onClose }) {
  const [mode, setMode] = useState('full')
  const [useRefImages, setUseRefImages] = useState(false)
  const [model, setModel] = useState(VEO_MODELS[0].value)
  const [sceneDuration, setSceneDuration] = useState(8)
  const [highlightDuration, setHighlightDuration] = useState(60)
  const [highlightStart, setHighlightStart] = useState(0)
  const [submitting, setSubmitting] = useState(false)

  const duration = clip?.metadata?.duration || 180
  const maxStart = Math.max(0, Math.round(duration) - 16)
  const effectiveHighlightDuration = Math.min(highlightDuration, Math.round(duration) - highlightStart)

  const sceneCount = mode === 'full'
    ? Math.ceil(duration / sceneDuration)
    : Math.ceil(effectiveHighlightDuration / sceneDuration)

  const handleSubmit = async () => {
    setSubmitting(true)
    try {
      await onSubmit({
        clip_id: clip.id,
        task_id: taskId,
        mode,
        use_ref_images: useRefImages,
        model,
        scene_duration: sceneDuration,
        highlight_duration: effectiveHighlightDuration,
        highlight_start: mode === 'highlight' ? highlightStart : 0,
      })
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={e => e.stopPropagation()}>
        <div className={styles.header}>
          <h2 className={styles.title}>生成 MV</h2>
          <button className={styles.closeBtn} onClick={onClose}>&times;</button>
        </div>

        <div className={styles.clipInfo}>
          {clip?.image_url && <img src={clip.image_url} alt="" className={styles.clipCover} />}
          <div>
            <div className={styles.clipTitle}>{clip?.title || 'Untitled'}</div>
            <div className={styles.clipMeta}>时长 {Math.round(duration)}s</div>
          </div>
        </div>

        <div className={styles.field}>
          <label className={styles.label}>MV 模式</label>
          <div className={styles.radioGroup}>
            <label className={`${styles.radio} ${mode === 'full' ? styles.radioActive : ''}`}>
              <input type="radio" name="mode" value="full" checked={mode === 'full'}
                onChange={() => setMode('full')} />
              <span>完整 MV</span>
              <small>覆盖整首歌</small>
            </label>
            <label className={`${styles.radio} ${mode === 'highlight' ? styles.radioActive : ''}`}>
              <input type="radio" name="mode" value="highlight" checked={mode === 'highlight'}
                onChange={() => setMode('highlight')} />
              <span>精华片段</span>
              <small>选取精彩部分</small>
            </label>
          </div>
        </div>

        {mode === 'highlight' && (
          <>
            <div className={styles.field}>
              <label className={styles.label}>起始位置 (秒)</label>
              <div className={styles.rangeRow}>
                <input type="range" className={styles.range}
                  value={highlightStart} min={0} max={maxStart} step={1}
                  onChange={e => setHighlightStart(Number(e.target.value))} />
                <input type="number" className={styles.input} style={{ width: 80 }}
                  value={highlightStart} min={0} max={maxStart} step={1}
                  onChange={e => setHighlightStart(Math.min(Number(e.target.value), maxStart))} />
              </div>
              <small className={styles.rangeHint}>
                选段范围: {highlightStart}s ~ {highlightStart + effectiveHighlightDuration}s
              </small>
            </div>
            <div className={styles.field}>
              <label className={styles.label}>精华时长 (秒)</label>
              <input type="number" className={styles.input} value={highlightDuration}
                min={16} max={Math.round(duration) - highlightStart} step={8}
                onChange={e => setHighlightDuration(Number(e.target.value))} />
            </div>
          </>
        )}

        <div className={styles.field}>
          <label className={styles.label}>每段视频时长</label>
          <div className={styles.radioGroup}>
            {[4, 6, 8].map(d => (
              <label key={d} className={`${styles.radio} ${sceneDuration === d ? styles.radioActive : ''}`}>
                <input type="radio" name="dur" value={d} checked={sceneDuration === d}
                  onChange={() => setSceneDuration(d)} />
                <span>{d} 秒</span>
              </label>
            ))}
          </div>
        </div>

        <div className={styles.field}>
          <label className={styles.label}>视频模型</label>
          <select className={styles.select} value={model} onChange={e => setModel(e.target.value)}>
            {VEO_MODELS.map(m => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
        </div>

        <div className={styles.field}>
          <label className={styles.checkLabel}>
            <input type="checkbox" checked={useRefImages}
              onChange={e => setUseRefImages(e.target.checked)} />
            <span>生成参考图 (Gemini Image)</span>
            <small className={styles.checkHint}>为每个场景先生成参考帧，提升视觉一致性，但会增加时间和费用</small>
          </label>
        </div>

        <div className={styles.summary}>
          预计生成 <strong>{sceneCount}</strong> 个视频片段，
          共 <strong>{sceneCount * sceneDuration}</strong> 秒
          {mode === 'highlight' && <span> (从 {highlightStart}s 开始)</span>}
          {useRefImages && <span> + {sceneCount} 张参考图</span>}
        </div>

        <div className={styles.actions}>
          <button className={styles.cancelBtn} onClick={onClose}>取消</button>
          <button className={styles.submitBtn} onClick={handleSubmit} disabled={submitting}>
            {submitting ? '提交中...' : '开始生成'}
          </button>
        </div>
      </div>
    </div>
  )
}
