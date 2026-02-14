import { useState, useEffect, useRef, useCallback } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { api } from '../api/client'
import { usePlayer } from '../context/PlayerContext'
import { MV_TERMINAL_STATUSES, MV_STATUS_LABELS } from '../utils/constants'
import StatusBadge from '../components/Common/StatusBadge'
import LoadingSpinner from '../components/Common/LoadingSpinner'
import styles from './MVDetail.module.css'

export default function MVDetail() {
  const { mvId } = useParams()
  const navigate = useNavigate()
  const { play, currentClip, isPlaying } = usePlayer()
  const [mv, setMV] = useState(null)
  const [loading, setLoading] = useState(true)
  const [activeScene, setActiveScene] = useState(0)
  const [downloading, setDownloading] = useState(false)
  const [videoError, setVideoError] = useState(null)
  const videoRef = useRef(null)
  const intervalRef = useRef(null)

  // 加载 MV 数据
  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const data = await api.getMV(mvId)
        if (mounted) { setMV(data); setLoading(false) }
      } catch {
        if (mounted) setLoading(false)
      }
    }
    load()
    return () => { mounted = false }
  }, [mvId])

  // 轮询非终态
  useEffect(() => {
    if (!mv || MV_TERMINAL_STATUSES.has(mv.status)) {
      clearInterval(intervalRef.current)
      return
    }
    intervalRef.current = setInterval(async () => {
      try {
        const data = await api.getMV(mvId)
        setMV(data)
      } catch { /* ignore */ }
    }, 5000)
    return () => clearInterval(intervalRef.current)
  }, [mv?.status, mvId])

  // 当活跃场景变化时切换视频
  const playScene = useCallback((index) => {
    setActiveScene(index)
    setVideoError(null)
    if (videoRef.current) {
      const scene = mv?.scenes?.[index]
      if (scene?.video_file) {
        videoRef.current.src = api.getMVSceneVideoUrl(mvId, index)
        videoRef.current.play().catch(() => {})
      }
    }
  }, [mv, mvId])

  // 视频结束时自动播放下一个
  const handleVideoEnded = useCallback(() => {
    const next = activeScene + 1
    if (next < (mv?.scenes?.length || 0)) {
      const nextScene = mv.scenes[next]
      if (nextScene?.video_file) {
        playScene(next)
        return
      }
    }
    // 循环
    if (mv?.scenes?.some(s => s.video_file)) {
      const first = mv.scenes.findIndex(s => s.video_file)
      if (first >= 0) playScene(first)
    }
  }, [activeScene, mv, playScene])

  // 视频加载失败
  const handleVideoError = useCallback(() => {
    setVideoError('视频加载失败，请检查后端服务是否正常运行')
  }, [])

  // 下载完整 MV
  const handleDownload = useCallback(async () => {
    setDownloading(true)
    try {
      await api.downloadMVFinal(mvId, `${mv?.clip_title || 'mv'}_${mvId.slice(0, 8)}.mp4`)
    } catch (err) {
      alert(err.message || '下载失败')
    } finally {
      setDownloading(false)
    }
  }, [mvId, mv?.clip_title])

  // 初始加载时自动选中第一个已完成的场景
  useEffect(() => {
    if (mv?.scenes?.length > 0 && videoRef.current) {
      const firstDone = mv.scenes.findIndex(s => s.video_file)
      if (firstDone >= 0 && !videoRef.current.src) {
        setActiveScene(firstDone)
        videoRef.current.src = api.getMVSceneVideoUrl(mvId, firstDone)
      }
    }
  }, [mv?.scenes, mvId])

  if (loading) return <LoadingSpinner />
  if (!mv) return <div style={{ color: 'var(--text-tertiary)', padding: 40 }}>MV 任务不存在</div>

  const isTerminal = MV_TERMINAL_STATUSES.has(mv.status)
  const totalScenes = mv.scenes?.length || 0
  const doneScenes = mv.scenes?.filter(s => s.status === 'done').length || 0
  const progress = totalScenes > 0 ? Math.round((doneScenes / totalScenes) * 100) : 0
  const statusLabel = MV_STATUS_LABELS[mv.status] || mv.status

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.header}>
        <button className={styles.backBtn} onClick={() => navigate(-1)}>&#8592;</button>
        <div className={styles.headerInfo}>
          <div className={styles.headerTitle}>MV: {mv.clip_title || mvId.slice(0, 8)}</div>
          <div className={styles.headerMeta}>
            <StatusBadge status={mv.status} label={statusLabel} />
            <span>{mv.mode === 'highlight' ? '精华片段' : '完整MV'}</span>
            <span>{totalScenes} 个场景</span>
          </div>
        </div>
      </div>

      {/* Progress */}
      {!isTerminal && (
        <div className={styles.section}>
          <div className={styles.progressBar}>
            <div className={styles.progressFill} style={{ width: `${progress}%` }} />
          </div>
          <div className={styles.progressText}>
            {statusLabel} · {doneScenes}/{totalScenes} 场景完成
          </div>
        </div>
      )}

      {/* Error */}
      {mv.error && (
        <div className={styles.errorBox}>{mv.error}</div>
      )}

      {/* Video Player */}
      {doneScenes > 0 && (
        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>MV 预览</h3>
          <div className={styles.playerArea}>
            <video
              ref={videoRef}
              className={styles.videoPlayer}
              onEnded={handleVideoEnded}
              onError={handleVideoError}
              onLoadStart={() => setVideoError(null)}
              controls
              playsInline
            />
            {videoError && (
              <div className={styles.errorBox}>{videoError}</div>
            )}
            <div className={styles.sceneNav}>
              <button
                className={styles.navBtn}
                disabled={activeScene <= 0}
                onClick={() => {
                  const prev = mv.scenes.findLastIndex((s, i) => i < activeScene && s.video_file)
                  if (prev >= 0) playScene(prev)
                }}
              >
                &#9664;&#9664;
              </button>
              <span className={styles.sceneLabel}>
                场景 {activeScene + 1} / {totalScenes}
              </span>
              <button
                className={styles.navBtn}
                disabled={activeScene >= totalScenes - 1}
                onClick={() => {
                  const next = mv.scenes.findIndex((s, i) => i > activeScene && s.video_file)
                  if (next >= 0) playScene(next)
                }}
              >
                &#9654;&#9654;
              </button>
            </div>
            {mv.video_path && (
              <button
                className={styles.downloadBtn}
                onClick={handleDownload}
                disabled={downloading}
              >
                {downloading ? '下载中...' : '下载完整 MV'}
              </button>
            )}
          </div>
        </div>
      )}

      {/* Scene Timeline */}
      {mv.storyboard?.length > 0 && (
        <div className={styles.section}>
          <h3 className={styles.sectionTitle}>分镜脚本</h3>
          <div className={styles.timeline}>
            {mv.storyboard.map((scene, i) => {
              const sceneState = mv.scenes?.[i] || {}
              const isDone = sceneState.status === 'done'
              const isFailed = sceneState.status === 'failed' || sceneState.status === 'timeout'
              const isActive = i === activeScene

              return (
                <div
                  key={i}
                  className={`${styles.sceneCard} ${isActive ? styles.sceneActive : ''} ${isDone ? styles.sceneDone : ''} ${isFailed ? styles.sceneFailed : ''}`}
                  onClick={() => isDone && playScene(i)}
                >
                  <div className={styles.sceneHeader}>
                    <span className={styles.sceneIndex}>#{i + 1}</span>
                    <span className={styles.sceneTime}>
                      {Math.round(scene.start_time)}s - {Math.round(scene.end_time)}s
                    </span>
                    <span className={`${styles.sceneDot} ${isDone ? styles.dotDone : isFailed ? styles.dotFailed : styles.dotPending}`} />
                  </div>

                  {sceneState.ref_image_file && (
                    <img
                      src={api.getMVSceneImageUrl(mvId, i)}
                      alt={`Scene ${i + 1} ref`}
                      className={styles.sceneRefImage}
                    />
                  )}

                  <div className={styles.sceneDesc}>{scene.description}</div>

                  {scene.mood && (
                    <div className={styles.sceneMood}>{scene.mood}</div>
                  )}

                  {scene.lyrics_section && (
                    <div className={styles.sceneLyrics}>{scene.lyrics_section}</div>
                  )}
                </div>
              )
            })}
          </div>
        </div>
      )}

      {/* Meta Info */}
      <div className={styles.section}>
        <h3 className={styles.sectionTitle}>详细信息</h3>
        <div className={styles.metaGrid}>
          <span className={styles.metaLabel}>MV ID</span>
          <span className={styles.metaValue}>{mv.mv_id}</span>
          <span className={styles.metaLabel}>Clip ID</span>
          <span className={styles.metaValue}>{mv.clip_id}</span>
          <span className={styles.metaLabel}>模型</span>
          <span className={styles.metaValue}>{mv.model}</span>
          <span className={styles.metaLabel}>每段时长</span>
          <span className={styles.metaValue}>{mv.scene_duration}s</span>
          <span className={styles.metaLabel}>参考图</span>
          <span className={styles.metaValue}>{mv.use_ref_images ? '是' : '否'}</span>
          {mv.finished_at && <>
            <span className={styles.metaLabel}>完成时间</span>
            <span className={styles.metaValue}>{new Date(mv.finished_at).toLocaleString()}</span>
          </>}
        </div>
      </div>
    </div>
  )
}
