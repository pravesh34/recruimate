import { useEffect } from 'react'
import { BrowserRouter, Navigate, Route, Routes, useLocation } from 'react-router-dom'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import ResumeAnalysis from './pages/ResumeAnalysis'
import JobCompatibility from './pages/JobCompatibility'
import SkillGap from './pages/SkillGap'
import InterviewPrep from './pages/InterviewPrep'
import MockInterview from './pages/MockInterview'
import Analytics from './pages/Analytics'
import Settings from './pages/Settings'

function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo({ top: 0, behavior: 'instant' })
  }, [pathname])
  return null
}

export default function App() {
  return (
    <BrowserRouter>
      <ScrollToTop />
      <Routes>
        <Route element={<Layout />}>
          <Route index element={<Dashboard />} />
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
  )
}
