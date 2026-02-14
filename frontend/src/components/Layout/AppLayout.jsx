import Sidebar from './Sidebar'
import PlayerBar from '../Player/PlayerBar'
import styles from './AppLayout.module.css'

export default function AppLayout({ children }) {
  return (
    <div className={styles.layout}>
      <Sidebar />
      <main className={styles.main}>{children}</main>
      <PlayerBar />
    </div>
  )
}
