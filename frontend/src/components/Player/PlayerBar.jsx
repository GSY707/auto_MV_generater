import { usePlayer } from '../../context/PlayerContext'
import { formatDuration } from '../../utils/formatTime'
import styles from './PlayerBar.module.css'

export default function PlayerBar() {
  const {
    currentClip, isPlaying, currentTime, duration, volume,
    toggle, seek, setVolume, playNext, playPrev,
  } = usePlayer()

  if (!currentClip) {
    return (
      <div className={styles.bar}>
        <div className={styles.empty}>没有正在播放的歌曲</div>
      </div>
    )
  }

  const handleSeek = (e) => {
    seek(Number(e.target.value))
  }

  const handleVolume = (e) => {
    setVolume(Number(e.target.value))
  }

  const toggleMute = () => {
    setVolume(volume > 0 ? 0 : 0.8)
  }

  const volumeIcon = volume === 0 ? '🔇' : volume < 0.5 ? '🔉' : '🔊'

  return (
    <div className={styles.bar}>
      <div className={styles.left}>
        <div className={styles.artwork}>
          {currentClip.image_url && <img src={currentClip.image_url} alt="" />}
        </div>
        <div className={styles.trackInfo}>
          <div className={styles.trackTitle}>{currentClip.title || 'Untitled'}</div>
          {currentClip.tags && <div className={styles.trackTags}>{currentClip.tags}</div>}
        </div>
      </div>

      <div className={styles.center}>
        <div className={styles.controls}>
          <button className={styles.controlBtn} onClick={playPrev}>⏮</button>
          <button className={styles.playBtn} onClick={toggle}>
            {isPlaying ? '⏸' : '▶'}
          </button>
          <button className={styles.controlBtn} onClick={playNext}>⏭</button>
        </div>
        <div className={styles.progressRow}>
          <span className={styles.time}>{formatDuration(currentTime)}</span>
          <input
            type="range"
            className={styles.slider}
            min={0}
            max={duration || 0}
            step={0.1}
            value={currentTime}
            onChange={handleSeek}
          />
          <span className={styles.time}>{formatDuration(duration)}</span>
        </div>
      </div>

      <div className={styles.right}>
        <span className={styles.volumeIcon} onClick={toggleMute}>{volumeIcon}</span>
        <input
          type="range"
          className={styles.volumeSlider}
          min={0}
          max={1}
          step={0.01}
          value={volume}
          onChange={handleVolume}
        />
      </div>
    </div>
  )
}
