import { useEffect, useState } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import {
  BarChart3,
  BrainCircuit,
  ChevronRight,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  MessagesSquare,
  Mic,
  Route,
  Search,
  Settings,
  Sparkles,
  Target,
  X,
} from 'lucide-react'
import { classNames } from '../services/utils'
import { useAuth } from '../services/auth'

const NAV = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, end: true },
  { to: '/jobs', label: 'Job search', icon: Search },
  { to: '/resume', label: 'Resume analysis', icon: FileText },
  { to: '/compatibility', label: 'Job compatibility', icon: Target },
  { to: '/skill-gap', label: 'Skill gap & roadmap', icon: Route },
  { to: '/interview-prep', label: 'Interview prep', icon: MessagesSquare },
  { to: '/mock-interview', label: 'Mock interview', icon: Mic },
  { to: '/analytics', label: 'Analytics', icon: BarChart3 },
  { to: '/settings', label: 'Settings', icon: Settings },
]

const TITLES = {
  '/': { title: 'Dashboard', subtitle: 'Your preparation at a glance' },
  '/jobs': { title: 'Job search', subtitle: 'Every posting ranked against your resume' },
  '/resume': { title: 'Resume analysis', subtitle: 'Extract, review and strengthen your resume' },
  '/compatibility': { title: 'Job compatibility', subtitle: 'See how your evidence maps to the role' },
  '/skill-gap': { title: 'Skill gap & roadmap', subtitle: 'Turn gaps into a focused learning plan' },
  '/interview-prep': { title: 'Interview prep', subtitle: 'A question bank built from your profile' },
  '/mock-interview': { title: 'Mock interview', subtitle: 'Practise one question at a time' },
  '/analytics': { title: 'Analytics', subtitle: 'Measure whether you are improving' },
  '/settings': { title: 'Settings', subtitle: 'Providers, routing and privacy' },
}

function Logo() {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-violet-600 shadow-lift">
        <BrainCircuit className="h-5 w-5 text-white" />
      </div>
      <div>
        <p className="text-[15px] font-bold tracking-tight text-white">RecruiMate</p>
        <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-brand-200/70">
          AI career coach
        </p>
      </div>
    </div>
  )
}

function Sidebar({ onNavigate }) {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const displayName = user?.display_name || 'Your workspace'
  const initials =
    displayName
      .split(' ')
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0])
      .join('')
      .toUpperCase() || 'RM'

  async function handleSignOut() {
    await logout()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex h-full flex-col bg-gradient-to-b from-brand-950 via-brand-900 to-[#111a3d]">
      <div className="flex items-center justify-between px-5 pb-6 pt-6">
        <Logo />
        <button
          onClick={onNavigate}
          className="rounded-lg p-1.5 text-brand-100/70 hover:bg-white/10 lg:hidden"
          aria-label="Close menu"
        >
          <X className="h-5 w-5" />
        </button>
      </div>
      <div className="px-4">
        <div className="rounded-xl border border-white/10 bg-white/5 p-3">
          <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-brand-200/80">
            <Sparkles className="h-3.5 w-3.5" /> Candidate workspace
          </div>
          <p className="mt-1.5 text-xs leading-relaxed text-brand-100/60">
            Prepare smarter with evidence-based feedback.
          </p>
        </div>
      </div>
      <nav className="scroll-thin mt-5 flex-1 space-y-1 overflow-y-auto px-3 pb-4">
        {NAV.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            className={({ isActive }) => classNames('nav-link', isActive && 'nav-link-active')}
          >
            <item.icon className="h-4 w-4 shrink-0" />
            <span>{item.label}</span>
            <ChevronRight className="ml-auto h-3.5 w-3.5 opacity-30" />
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-white/10 p-4">
        <NavLink
          to="/settings"
          onClick={onNavigate}
          className="block rounded-xl bg-white/5 p-3 transition hover:bg-white/10"
        >
          <div className="flex items-center justify-between">
            <span className="text-[11px] font-semibold uppercase tracking-wider text-brand-200/70">
              Provider
            </span>
            <span className="flex items-center gap-1 text-[10px] font-semibold text-emerald-300">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" /> local-ready
            </span>
          </div>
          <p className="mt-1 text-xs text-brand-100/60">Heuristic mode works offline. Connect a model for deeper answers.</p>
        </NavLink>
        <div className="mt-3 flex items-center gap-2 px-1">
          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-brand-500/30 text-xs font-bold text-white">
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-xs font-semibold text-white">{displayName}</p>
            <p className="truncate text-[10px] text-brand-200/60">{user?.email || 'Local & private'}</p>
          </div>
          {user && (
            <button
              type="button"
              onClick={handleSignOut}
              title="Sign out"
              className="rounded-lg p-1.5 text-brand-100/70 transition hover:bg-white/10 hover:text-white"
            >
              <LogOut className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export default function Layout() {
  const [open, setOpen] = useState(false)
  const location = useLocation()
  const meta = TITLES[location.pathname] || {
    title: 'RecruiMate',
    subtitle: 'Your AI career and interview coach',
  }

  useEffect(() => {
    setOpen(false)
  }, [location.pathname])

  return (
    <div className="min-h-screen lg:flex">
      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 lg:block">
        <Sidebar />
      </aside>
      {open && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div className="absolute inset-0 bg-ink-900/50 backdrop-blur-sm" onClick={() => setOpen(false)} />
          <aside className="absolute inset-y-0 left-0 w-72 animate-fade-up shadow-2xl">
            <Sidebar onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col lg:pl-64">
        <header className="sticky top-0 z-30 border-b border-ink-200/70 bg-ink-50/85 backdrop-blur-xl">
          <div className="flex items-center gap-3 px-4 py-3.5 sm:px-6 lg:px-8">
            <button
              className="rounded-lg p-2 text-ink-600 hover:bg-ink-100 lg:hidden"
              onClick={() => setOpen(true)}
              aria-label="Open menu"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div className="min-w-0 flex-1">
              <h1 className="truncate text-base font-semibold tracking-tight text-ink-900 sm:text-lg">
                {meta.title}
              </h1>
              <p className="hidden truncate text-xs text-ink-500 sm:block">{meta.subtitle}</p>
            </div>
            <NavLink to="/resume" className="btn-primary btn-sm hidden sm:inline-flex">
              <FileText className="h-3.5 w-3.5" /> Upload resume
            </NavLink>
          </div>
        </header>
        <main className="mx-auto w-full max-w-7xl flex-1 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
        <footer className="mx-auto w-full max-w-7xl px-4 pb-6 text-center text-[11px] leading-relaxed text-ink-400 sm:px-6 lg:px-8">
          RecruiMate provides preparation support, not hiring decisions. Your resume is processed on your
          device unless you configure an external provider.
        </footer>
      </div>
    </div>
  )
}
