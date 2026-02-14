import ClipCard from './ClipCard'

export default function ClipList({ clips }) {
  if (!clips || clips.length === 0) return null
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {clips.map(clip => <ClipCard key={clip.id} clip={clip} />)}
    </div>
  )
}
