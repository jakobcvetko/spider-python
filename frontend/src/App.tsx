import { Navigate, Route, Routes } from 'react-router-dom'

import { ProtectedRoute } from './components/ProtectedRoute'
import AdminPage from './pages/AdminPage'
import AdminAvtoNetPage from './pages/AdminAvtoNetPage'
import AdminBolhaAdStatesPage from './pages/AdminBolhaAdStatesPage'
import AdminBolhaPage from './pages/AdminBolhaPage'
import ListingsPage from './pages/ListingsPage'
import LoginPage from './pages/LoginPage'
import RegisterPage from './pages/RegisterPage'

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route
        path="/"
        element={
          <ProtectedRoute>
            <ListingsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/bolha/ad-states"
        element={
          <ProtectedRoute>
            <AdminBolhaAdStatesPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/bolha"
        element={
          <ProtectedRoute>
            <AdminBolhaPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin/avto-net"
        element={
          <ProtectedRoute>
            <AdminAvtoNetPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/admin"
        element={
          <ProtectedRoute>
            <AdminPage />
          </ProtectedRoute>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
