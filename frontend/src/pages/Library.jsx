import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { usePlayer } from '../context/PlayerContext'
import GlassCard from '../components/Common/GlassCard'
import LoadingSpinner from '../components/Common/LoadingSpinner'
import EmptyState from '../components/Common/EmptyState'
import styles from './Library.module.css'

function formatFileSize(bytes) {
  if (!bytes) return ''
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1048576) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1048576).toFixed(1)} MB`
}

export default function Library() {
  const [files, setFiles] = useState([])
  const [loading, setLoading] = useState(true)
  const { play } = usePlayer()

  useEffect(() => {
    api.getOutputFiles()
      .then(data => setFiles(Array.isArray(data) ? data : []))
      .catch(() => setFiles([]))
      .finally(() => setLoading(false))
  }, [])

  if (loading) return <LoadingSpinner />

  const mp3s = files.filter(f => f.name?.endsWith('.mp3'))
  const images = files.filter(f => /\.(jpg|jpeg|png)$/i.test(f.name))

  if (files.length === 0) {
    return (
      <div className={styles.page}>
        <h1 className="page-title">媒体库</h1>
        <EmptyState
          icon="📁"
          title="媒体库为空"
          subtitle="完成音乐生成后，文件会自动保存到这里"
        />
      </div>
    )
  }

  const handlePlayMp3 = (file) => {
    play({
      id: file.name,
      title: file.name.replace('.mp3', ''),
      audio_url: `/api/output/${file.name}`,
    })
  }

  return (
    <div className={styles.page}>
      <h1 className="page-title">媒体库</h1>

      {mp3s.length > 0 && (
        <div className={styles.section}>
          <h2 className={styles.sectionTitle}>音频文件</h2>
          <div className={styles.grid}>
            {mp3s.map(f => (
              <GlassCard key={f.name} className={styles.fileCard} onClick={() => handlePlayMp3(f)}>
                <div className={styles.fileIcon}>♪</div>
                <div className={styles.fileInfo}>
                  <div className={styles.fileName}>{f.name}</div>
                  <div className={styles.fileMeta}>{formatFileSize(f.size)}</div>
                </div>
                <button className={styles.actionBtn} onClick={(e) => { e.stopPropagation(); handlePlayMp3(f) }}>▶</button>
              </GlassCard>
            ))}
          </div>
        </div>
      )}

      {images.length > 0 && (
        <div className={styles.section}>
          <h2 className={styles.sectionTitle}>封面图片</h2>
          <div className={styles.imageGrid}>
            {images.map(f => (
              <div key={f.name} className={styles.imageCard}>
                <img src={`/api/output/${f.name}`} alt={f.name} />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
