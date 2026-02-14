import styles from './GlassCard.module.css'

export default function GlassCard({ children, className, onClick, hover = true }) {
  return (
    <div
      className={`${styles.card} ${hover ? styles.hover : ''} ${className || ''}`}
      onClick={onClick}
    >
      {children}
    </div>
  )
}
