import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import NewRun from './pages/NewRun'
import RunDetails from './pages/RunDetails'
import TrustRegistry from './pages/TrustRegistry'
import Integrations from './pages/Integrations'
import Login from './pages/Login'

function ProtectedRoute({ children }) {
  const token = localStorage.getItem('aura_token')
  if (!token) return <Navigate to="/login" replace />
  return <Layout>{children}</Layout>
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<Login />} />
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/dashboard"    element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
      <Route path="/new"          element={<ProtectedRoute><NewRun /></ProtectedRoute>} />
      <Route path="/runs/:runId"  element={<ProtectedRoute><RunDetails /></ProtectedRoute>} />
      <Route path="/trust"        element={<ProtectedRoute><TrustRegistry /></ProtectedRoute>} />
      <Route path="/integrations" element={<ProtectedRoute><Integrations /></ProtectedRoute>} />
    </Routes>
  )
}
