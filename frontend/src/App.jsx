import React from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import NewRun from './pages/NewRun'
import RunDetails from './pages/RunDetails'
import TrustRegistry from './pages/TrustRegistry'
import Integrations from './pages/Integrations'

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Navigate to="/dashboard" replace />} />
      <Route path="/dashboard"    element={<Layout><Dashboard /></Layout>} />
      <Route path="/new"          element={<Layout><NewRun /></Layout>} />
      <Route path="/runs/:runId"  element={<Layout><RunDetails /></Layout>} />
      <Route path="/trust"        element={<Layout><TrustRegistry /></Layout>} />
      <Route path="/integrations" element={<Layout><Integrations /></Layout>} />
    </Routes>
  )
}
