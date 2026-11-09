import { Navigate, Route, Routes, useLocation } from 'react-router-dom'
import { useAuth } from './hooks/useAuth'
import Layout from './components/Layout'
import { Spinner } from './components/ui'
import AgentsPage from './pages/AgentsPage'
import ChainsPage from './pages/ChainsPage'
import ChatPage from './pages/ChatPage'
import Dashboard from './pages/Dashboard'
import DocumentsPage from './pages/DocumentsPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'

function FullScreenSpinner() {
  return (
    <div className="flex h-full items-center justify-center text-slate-500">
      <Spinner className="h-6 w-6" />
    </div>
  )
}

function RequireAuth({ children }) {
  const { isAuthenticated, loading } = useAuth()
  const location = useLocation()
  if (loading) return <FullScreenSpinner />
  if (!isAuthenticated) return <Navigate to="/login" replace state={{ from: location.pathname + location.search }} />
  return children
}

function GuestOnly({ children }) {
  const { isAuthenticated, loading } = useAuth()
  if (loading) return <FullScreenSpinner />
  return isAuthenticated ? <Navigate to="/" replace /> : children
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<GuestOnly><LoginPage /></GuestOnly>} />
      <Route path="/register" element={<GuestOnly><RegisterPage /></GuestOnly>} />
      <Route
        element={
          <RequireAuth>
            <Layout />
          </RequireAuth>
        }
      >
        <Route index element={<Dashboard />} />
        <Route path="agents" element={<AgentsPage />} />
        <Route path="chat" element={<ChatPage />} />
        <Route path="chat/:agentId" element={<ChatPage />} />
        <Route path="documents" element={<DocumentsPage />} />
        <Route path="chains" element={<ChainsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
