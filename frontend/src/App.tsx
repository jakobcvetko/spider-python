import { Navigate, Route, Routes } from 'react-router-dom'

import { AdminLayout } from './components/AdminLayout'
import { ProtectedRoute } from './components/ProtectedRoute'
import AdminPage from './pages/AdminPage'
import AdminAvtoNetPage from './pages/AdminAvtoNetPage'
import AdminBolhaPage from './pages/AdminBolhaPage'
import AdminListingsPage from './pages/AdminListingsPage'
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
        path="/admin"
        element={
          <ProtectedRoute>
            <AdminLayout />
          </ProtectedRoute>
        }
      >
        <Route index element={<AdminPage />} />
        <Route path="listings" element={<AdminListingsPage />} />
        <Route path="bolha" element={<AdminBolhaPage />} />
        <Route path="bolha/ads" element={<Navigate to="/admin/bolha" replace />} />
        <Route path="bolha/ad-states" element={<Navigate to="/admin/bolha" replace />} />
        <Route path="avtonet" element={<AdminAvtoNetPage />} />
        <Route path="avto-net" element={<Navigate to="/admin/avtonet" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}
