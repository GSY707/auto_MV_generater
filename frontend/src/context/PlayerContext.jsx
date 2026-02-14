import { createContext, useContext, useState, useRef, useEffect, useCallback } from 'react'

const PlayerContext = createContext(null)

export function PlayerProvider({ children }) {
  const [currentClip, setCurrentClip] = useState(null)
  const [isPlaying, setIsPlaying] = useState(false)
  const [currentTime, setCurrentTime] = useState(0)
  const [duration, setDuration] = useState(0)
  const [volume, setVolumeState] = useState(0.8)
  const [playlist, setPlaylist] = useState([])
  const audioRef = useRef(null)

  useEffect(() => {
    const audio = new Audio()
    audio.volume = 0.8
    audioRef.current = audio

    const onTime = () => setCurrentTime(audio.currentTime)
    const onMeta = () => setDuration(audio.duration || 0)
    const onEnded = () => {
      setIsPlaying(false)
      setCurrentTime(0)
    }

    audio.addEventListener('timeupdate', onTime)
    audio.addEventListener('loadedmetadata', onMeta)
    audio.addEventListener('ended', onEnded)

    return () => {
      audio.removeEventListener('timeupdate', onTime)
      audio.removeEventListener('loadedmetadata', onMeta)
      audio.removeEventListener('ended', onEnded)
      audio.pause()
      audio.src = ''
    }
  }, [])

  const play = useCallback((clip) => {
    const audio = audioRef.current
    if (!audio) return
    if (clip && clip.audio_url) {
      if (!currentClip || currentClip.id !== clip.id) {
        setCurrentClip(clip)
        audio.src = clip.audio_url
        audio.load()
      }
      audio.play().catch(console.error)
      setIsPlaying(true)
    }
  }, [currentClip])

  const pause = useCallback(() => {
    audioRef.current?.pause()
    setIsPlaying(false)
  }, [])

  const toggle = useCallback(() => {
    if (!currentClip) return
    if (isPlaying) {
      pause()
    } else {
      audioRef.current?.play().catch(console.error)
      setIsPlaying(true)
    }
  }, [currentClip, isPlaying, pause])

  const seek = useCallback((time) => {
    if (audioRef.current) {
      audioRef.current.currentTime = time
      setCurrentTime(time)
    }
  }, [])

  const setVolume = useCallback((vol) => {
    const v = Math.max(0, Math.min(1, vol))
    setVolumeState(v)
    if (audioRef.current) audioRef.current.volume = v
  }, [])

  const playNext = useCallback(() => {
    if (!currentClip || playlist.length === 0) return
    const idx = playlist.findIndex(c => c.id === currentClip.id)
    const next = playlist[(idx + 1) % playlist.length]
    if (next) play(next)
  }, [currentClip, playlist, play])

  const playPrev = useCallback(() => {
    if (!currentClip || playlist.length === 0) return
    const idx = playlist.findIndex(c => c.id === currentClip.id)
    const prev = playlist[(idx - 1 + playlist.length) % playlist.length]
    if (prev) play(prev)
  }, [currentClip, playlist, play])

  return (
    <PlayerContext.Provider value={{
      currentClip, isPlaying, currentTime, duration, volume,
      play, pause, toggle, seek, setVolume,
      playlist, setPlaylist, playNext, playPrev
    }}>
      {children}
    </PlayerContext.Provider>
  )
}

export function usePlayer() {
  const ctx = useContext(PlayerContext)
  if (!ctx) throw new Error('usePlayer must be used within PlayerProvider')
  return ctx
}
