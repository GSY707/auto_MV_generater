import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react'
import { api } from '../api/client'
import { TERMINAL_STATUSES } from '../utils/constants'

const TaskContext = createContext(null)

export function TaskProvider({ children }) {
  const [tasks, setTasks] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const intervalRef = useRef(null)
  const tasksRef = useRef(tasks)
  tasksRef.current = tasks

  const fetchTasks = useCallback(async () => {
    try {
      const data = await api.getTasks()
      setTasks(Array.isArray(data) ? data : [])
      setError(null)
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchTasks()
  }, [fetchTasks])

  useEffect(() => {
    intervalRef.current = setInterval(async () => {
      const active = tasksRef.current
        .filter(t => !TERMINAL_STATUSES.has(t.status))
        .map(t => t.task_id)
      if (active.length === 0) return
      try {
        const updated = await api.refreshTasks(active)
        if (!Array.isArray(updated)) return
        setTasks(prev => {
          const map = new Map(prev.map(t => [t.task_id, t]))
          updated.forEach(t => map.set(t.task_id, t))
          return Array.from(map.values()).sort(
            (a, b) => new Date(b.created_at || 0) - new Date(a.created_at || 0)
          )
        })
      } catch (err) {
        console.error('Refresh failed:', err)
      }
    }, 5000)
    return () => clearInterval(intervalRef.current)
  }, [])

  const addTask = useCallback((task) => {
    setTasks(prev => [task, ...prev])
  }, [])

  const refreshTask = useCallback(async (taskId) => {
    try {
      const data = await api.getTask(taskId)
      setTasks(prev => prev.map(t => t.task_id === taskId ? data : t))
      return data
    } catch (err) {
      console.error('Refresh task failed:', err)
    }
  }, [])

  const deleteTask = useCallback(async (taskId) => {
    try {
      await api.deleteTask(taskId)
      setTasks(prev => prev.filter(t => t.task_id !== taskId))
      return true
    } catch (err) {
      console.error('Delete task failed:', err)
      return false
    }
  }, [])

  return (
    <TaskContext.Provider value={{ tasks, loading, error, addTask, refreshTask, fetchTasks, deleteTask }}>
      {children}
    </TaskContext.Provider>
  )
}

export function useTasks() {
  const ctx = useContext(TaskContext)
  if (!ctx) throw new Error('useTasks must be used within TaskProvider')
  return ctx
}
