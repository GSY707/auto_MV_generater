import { NavLink } from 'react-router-dom'
import styles from './Sidebar.module.css'

const navItems = [
  { to: '/', label: 'Dashboard', icon: '\u229E' },
  { to: '/create', label: '\u521B\u4F5C', icon: '\uFF0B' },
  { to: '/chat', label: 'AI \u52A9\u624B', icon: '\u25CE' },
  { to: '/library', label: '\u5A92\u4F53\u5E93', icon: '\u266B' },
]

export default function Sidebar() {
  return (
    <aside className={styles.sidebar}>
      <div className={styles.logo}>
        <div className={styles.logoIcon}>♪</div>
        <span className={styles.logoText}>MusicAI</span>
      </div>
      <nav className={styles.nav}>
        {navItems.map(item => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === '/'}
            className={({ isActive }) =>
              `${styles.navLink} ${isActive ? styles.active : ''}`
            }
          >
            <span className={styles.navIcon}>{item.icon}</span>
            {item.label}
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
