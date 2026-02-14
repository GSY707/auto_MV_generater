import styles from './EmptyState.module.css'

export default function EmptyState({ icon, title, subtitle, actionLabel, onAction }) {
  return (
    <div className={styles.empty}>
      {icon && <div className={styles.icon}>{icon}</div>}
      <div className={styles.title}>{title}</div>
      {subtitle && <div className={styles.subtitle}>{subtitle}</div>}
      {actionLabel && onAction && (
        <button className={styles.action} onClick={onAction}>{actionLabel}</button>
      )}
    </div>
  )
}
