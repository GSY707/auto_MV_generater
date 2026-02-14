import { SUNO_MODELS } from '../../utils/constants'
import styles from './ModelSelector.module.css'

export default function ModelSelector({ value, onChange }) {
  return (
    <select
      className={styles.select}
      value={value}
      onChange={e => onChange(e.target.value)}
    >
      {SUNO_MODELS.map(m => (
        <option key={m.value} value={m.value}>{m.label}</option>
      ))}
    </select>
  )
}
