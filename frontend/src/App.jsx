import { useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Layout from './components/Layout'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import JobSearch from './pages/JobSearch'
import ResumeAnalysis from './pages/ResumeAnalysis'
import JobCompatibility from './pages/JobCompatibility'
import SkillGap from './pages/SkillGap'
import InterviewPrep from './pages/InterviewPrep'
import MockInterview from './pages/MockInterview'
import Analytics from './pages/Analytics'
import Settings from './pages/Settings'
import { AuthProvider, useAuth } from './services/auth'
import { LoadingBlock } from './components/ui'

function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' })
  }, [pathname])
  return null
}

function RequireAuth({ children }) {
  const { user, loading, authEnabled } = useAuth()
  if (loading) return <LoadingBlock label="Checking your session…" />
  // When auth is off the app runs in trusted-local mode, so let everyone in.
  if (!authEnabled) return children
  if (!user) return <Navigate to="/login" replace />
  return children
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <ScrollToTop />
        <Routes>
          <Route path="login" element={<Login />} />
          <Route
            element={
              <RequireAuth>
                <Layout />
              </RequireAuth>
            }
          >
            <Route index element={<Dashboard />} />
            <Route path="jobs" element={<JobSearch />} />
            <Route path="resume" element={<ResumeAnalysis />} />
            <Route path="compatibility" element={<JobCompatibility />} />
            <Route path="skill-gap" element={<SkillGap />} />
            <Route path="interview-prep" element={<InterviewPrep />} />
            <Route path="mock-interview" element={<MockInterview />} />
            <Route path="mock-interview/:id" element={<MockInterview />} />
            <Route path="analytics" element={<Analytics />} />
            <Route path="settings" element={<Settings />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  )
}
