import { useState } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { BrainCircuit, Loader2, LogIn, ShieldCheck, UserPlus } from 'lucide-react'
import { useAuth } from '../services/auth'
import { apiError } from '../services/api'

const DEMO_ACCOUNTS = [
  { email: 'candidate1@example.com', name: 'Aarav Sharma', role: 'AI/ML undergraduate' },
  { email: 'candidate2@example.com', name: 'Diya Patel', role: 'Data scientist' },
  { email: 'candidate3@example.com', name: 'Arjun Menon', role: 'Backend engineer' },
  { email: 'candidate4@example.com', name: 'Ishita Rao', role: 'MLOps engineer' },
  { email: 'candidate5@example.com', name: 'Kabir Nair', role: 'LLM engineer' },
]
const DEMO_PASSWORD = 'RecruiMate@123'

export default function Login() {
  const { user, loading, authEnabled, login, register } = useAuth()
  const navigate = useNavigate()
  const [mode, setMode] = useState('login')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  if (!loading && !authEnabled) return <Navigate to="/" replace />
  if (!loading && user) return <Navigate to="/" replace />

  async function submit(event) {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      if (mode === 'login') {
        await login(email, password)
      } else {
        await register(email, password, displayName)
      }
      navigate('/', { replace: true })
    } catch (e) {
      setError(apiError(e))
    } finally {
      setBusy(false)
    }
  }

  async function useDemo(account) {
    setError('')
    setBusy(true)
    try {
      await login(account.email, DEMO_PASSWORD)
      navigate('/', { replace: true })
    } catch (e) {
      setError(apiError(e))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-950 via-brand-900 to-[#111a3d] px-4 py-10">
      <div className="w-full max-w-5xl">
        <div className="grid gap-6 lg:grid-cols-5">
          <div className="lg:col-span-2">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-gradient-to-br from-brand-500 to-violet-600 shadow-lift">
                <BrainCircuit className="h-5 w-5 text-white" />
              </div>
              <div>
                <p className="text-[15px] font-bold tracking-tight text-white">RecruiMate</p>
                <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-brand-200/70">
                  AI career coach
                </p>
              </div>
            </div>
            <h1 className="mt-6 text-2xl font-bold tracking-tight text-white">
              Sign in to your workspace.
            </h1>
            <p className="mt-2 text-sm leading-relaxed text-brand-100/70">
              Your resumes, analyses and interview history are private to your account.
            </p>

            <div className="mt-6 rounded-2xl border border-white/10 bg-white/5 p-4">
              <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-brand-200/80">
                <ShieldCheck className="h-3.5 w-3.5" /> Demo accounts
              </p>
              <ul className="mt-3 space-y-1.5">
                {DEMO_ACCOUNTS.map((account) => (
                  <li key={account.email}>
                    <button
                      type="button"
                      onClick={() => useDemo(account)}
                      disabled={busy}
                      className="w-full rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-left transition hover:bg-white/10 disabled:opacity-50"
                    >
                      <p className="text-xs font-semibold text-white">{account.name}</p>
                      <p className="text-[11px] text-brand-100/60">
                        {account.role} · {account.email}
                      </p>
                    </button>
                  </li>
                ))}
              </ul>
              <p className="mt-3 text-[11px] text-brand-100/50">
                All demo accounts use the password <span className="font-mono text-brand-100/80">{DEMO_PASSWORD}</span>
              </p>
            </div>
          </div>

          <div className="lg:col-span-3">
            <div className="rounded-3xl bg-white p-6 shadow-lift sm:p-8">
              <div className="mb-5 flex gap-1 rounded-xl bg-ink-100 p-1">
                <button
                  type="button"
                  onClick={() => setMode('login')}
                  className={`flex-1 rounded-lg px-3 py-2 text-sm font-semibold transition ${
                    mode === 'login' ? 'bg-white text-ink-900 shadow-sm' : 'text-ink-500'
                  }`}
                >
                  <LogIn className="mr-1.5 inline h-4 w-4" /> Sign in
                </button>
                <button
                  type="button"
                  onClick={() => setMode('register')}
                  className={`flex-1 rounded-lg px-3 py-2 text-sm font-semibold transition ${
                    mode === 'register' ? 'bg-white text-ink-900 shadow-sm' : 'text-ink-500'
                  }`}
                >
                  <UserPlus className="mr-1.5 inline h-4 w-4" /> Create account
                </button>
              </div>

              {error && (
                <div className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                  {error}
                </div>
              )}

              <form onSubmit={submit} className="space-y-4">
                {mode === 'register' && (
                  <div>
                    <label className="mb-1.5 block text-xs font-semibold text-ink-600">Full name</label>
                    <input
                      type="text"
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      placeholder="Your name"
                      className="w-full rounded-xl border border-ink-200 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
                    />
                  </div>
                )}
                <div>
                  <label className="mb-1.5 block text-xs font-semibold text-ink-600">Email</label>
                  <input
                    type="email"
                    required
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="you@example.com"
                    className="w-full rounded-xl border border-ink-200 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
                  />
                </div>
                <div>
                  <label className="mb-1.5 block text-xs font-semibold text-ink-600">Password</label>
                  <input
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={mode === 'register' ? '8+ chars, upper, lower, digit' : 'Your password'}
                    className="w-full rounded-xl border border-ink-200 px-3 py-2.5 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
                  />
                </div>
                <button type="submit" disabled={busy} className="btn-primary w-full justify-center">
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                  {mode === 'login' ? 'Sign in' : 'Create account'}
                </button>
              </form>

              <p className="mt-4 text-center text-[11px] text-ink-400">
                Data stays on your device. See the{' '}
                <Link to="/settings" className="font-semibold text-brand-600">
                  privacy settings
                </Link>{' '}
                for details.
              </p>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
