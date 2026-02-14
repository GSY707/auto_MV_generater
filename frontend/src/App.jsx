import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { TaskProvider } from './context/TaskContext'
import { PlayerProvider } from './context/PlayerContext'
import AppLayout from './components/Layout/AppLayout'
import Dashboard from './pages/Dashboard'
import Create from './pages/Create'
import TaskDetail from './pages/TaskDetail'
import MVDetail from './pages/MVDetail'
import Chat from './pages/Chat'
import Library from './pages/Library'

export default function App() {
  return (
    <BrowserRouter>
      <TaskProvider>
        <PlayerProvider>
          <AppLayout>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/create" element={<Create />} />
              <Route path="/task/:taskId" element={<TaskDetail />} />
              <Route path="/mv/:mvId" element={<MVDetail />} />
              <Route path="/chat" element={<Chat />} />
              <Route path="/library" element={<Library />} />
            </Routes>
          </AppLayout>
        </PlayerProvider>
      </TaskProvider>
    </BrowserRouter>
  )
}
