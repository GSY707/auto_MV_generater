import { usePlayer } from '../../context/PlayerContext'
import { formatDuration } from '../../utils/formatTime'
import GlassCard from '../Common/GlassCard'
import styles from './ClipCard.module.css'

export default function ClipCard({ clip }) {
  const { play, currentClip, isPlaying, toggle } = usePlayer()
  const isCurrent = currentClip?.id === clip.id

  const handlePlay = () => {
    if (isCurrent) {
      toggle()
    } else {
      play(clip)
    }
  }

  return (
    <GlassCard className={styles.card} hover={false}>
      <div className={styles.artwork}>
        {clip.image_url && <img src={clip.image_large_url || clip.image_url} alt={clip.title} />}
        <button className={styles.playBtn} onClick={handlePlay}>
          <span className={styles.playIcon}>
            {isCurrent && isPlaying ? '⏸' : '▶'}
          </span>
        </button>
      </div>
      <div className={styles.info}>
        <div className={styles.title}>{clip.title || 'Untitled'}</div>
        {clip.tags && <div className={styles.tags}>{clip.tags}</div>}
        <div className={styles.meta}>
          {clip.metadata?.duration && <span>{formatDuration(clip.metadata.duration)}</span>}
          {clip.metadata?.type && <span>{clip.metadata.type}</span>}
        </div>
        <div className={styles.actions}>
          {clip.audio_url && (
            <a className={styles.actionBtn} href={clip.audio_url} target="_blank" rel="noreferrer">
              MP3
            </a>
          )}
        </div>
      </div>
    </GlassCard>
  )
}
