import { useEffect, useState } from 'react'
import {
  Activity,
  Cpu,
  Database,
  Loader2,
  Lock,
  RefreshCw,
  Save,
  ShieldCheck,
  Trash2,
  TriangleAlert,
  Workflow,
} from 'lucide-react'
import api, { apiError } from '../services/api'
import { classNames, fmtDateTime } from '../services/utils'
import GatewaySelector from '../components/GatewaySelector'
import { Badge, ErrorBanner, LoadingBlock, SectionHeading } from '../components/ui'

const PROVIDER_ORDER = ['heuristic', 'openrouter', 'groq', 'gemini', 'opencode', 'ollama', 'custom']

export default function Settings() {
  const [data, setData] = useState(null)
  const [health, setHealth] = useState({})
  const [usage, setUsage] = useState(null)
  const [account, setAccount] = useState(null)
  const [routing, setRouting] = useState({ default_provider: 'heuristic', agent_overrides: {} })
  const [loading, setLoading] = useState(true)
  const [healthLoading, setHealthLoading] = useState(false)
  const [routingSaving, setRoutingSaving] = useState(false)
  const [deleting, setDeleting] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')

  async function fetchProviders() {
    const providers = await api.getProviders()
    setData(providers)
    setRouting({
      default_provider: providers.routing?.default_provider || 'heuristic',
      agent_overrides: providers.routing?.agent_overrides || {},
    })
  }

  useEffect(() => {
    Promise.allSettled([fetchProviders(), api.getUsage(), api.getAccount()])
      .then(([providersRes, usageRes, accountRes]) => {
        if (providersRes.status === 'rejected') setError(apiError(providersRes.reason))
        if (usageRes.status === 'fulfilled') setUsage(usageRes.value)
        if (accountRes.status === 'fulfilled') setAccount(accountRes.value)
      })
      .finally(() => setLoading(false))
  }, [])

  async function refreshHealth() {
    setHealthLoading(true)
    setNotice('')
    try {
      const result = await api.getProviderHealth()
      const map = {}
      for (const item of result.providers || []) map[item.provider] = item
      setHealth(map)
    } catch (e) {
      setError(apiError(e))
    } finally {
      setHealthLoading(false)
    }
  }

  async function saveProvider(payload) {
    setError('')
    try {
      await api.updateProvider(payload)
      await fetchProviders()
      setNotice(`${payload.provider} configuration saved.`)
      setHealth((current) => ({ ...current, [payload.provider]: undefined }))
    } catch (e) {
      setError(apiError(e))
      throw e
    }
  }

  async function testProvider(provider, model) {
    const result = await api.testProvider(provider, model)
    setHealth((current) => ({
      ...current,
      [provider]: {
        provider,
        configured: true,
        healthy: result.healthy,
        detail: result.detail,
        latency_ms: result.latency_ms,
        model: result.model,
      },
    }))
    return result
  }

  async function loadModels(provider) {
    try {
      const result = await api.getProviderModels(provider)
      return result.models
    } catch (e) {
      setError(apiError(e))
      return []
    }
  }

  async function saveRouting() {
    setRoutingSaving(true)
    setError('')
    try {
      const payload = {
        default_provider: routing.default_provider,
        agent_overrides: Object.fromEntries(
          Object.entries(routing.agent_overrides || {}).filter(([, value]) => value?.provider),
        ),
      }
      const result = await api.updateRouting(payload)
      setRouting({
        default_provider: result.routing.default_provider,
        agent_overrides: result.routing.agent_overrides || {},
      })
      setNotice('Routing saved. New agent runs will use this configuration.')
      await fetchProviders()
    } catch (e) {
      setError(apiError(e))
    } finally {
      setRoutingSaving(false)
    }
  }

  function setOverride(agentId, field, value) {
    setRouting((current) => {
      const existing = current.agent_overrides?.[agentId] || { provider: '', model: '' }
      const next = { ...existing, [field]: value }
      if (field === 'provider' && !value) {
        const overrides = { ...current.agent_overrides }
        delete overrides[agentId]
        return { ...current, agent_overrides: overrides }
      }
      return { ...current, agent_overrides: { ...current.agent_overrides, [agentId]: next } }
    })
  }

  async function deleteData() {
    if (!window.confirm('Delete ALL resumes, analyses, interviews, roadmaps, provider credentials and logs? This cannot be undone.')) return
    if (!window.confirm('Final confirmation: permanently delete all RecruiMate data on this device?')) return
    setDeleting(true)
    try {
      await api.deleteAllData()
      setNotice('All local data was deleted.')
      setUsage(null)
      setAccount(null)
      await fetchProviders()
    } catch (e) {
      setError(apiError(e))
    } finally {
      setDeleting(false)
    }
  }

  if (loading) return <LoadingBlock label="Loading provider settings…" />

  const providers = [...(data?.providers || [])].sort(
    (a, b) => PROVIDER_ORDER.indexOf(a.provider) - PROVIDER_ORDER.indexOf(b.provider),
  )
  const agents = data?.agents || []

  return (
    <div className="space-y-6">
      <ErrorBanner message={error} onDismiss={() => setError('')} />
      {notice && (
        <div className="flex items-center justify-between gap-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
          <span>{notice}</span>
          <button className="text-xs font-semibold hover:underline" onClick={() => setNotice('')}>Dismiss</button>
        </div>
      )}

      <div className="rounded-2xl border border-brand-200 bg-brand-50/70 p-4">
        <div className="flex flex-start gap-3">
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-brand-600" />
          <div>
            <p className="text-sm font-semibold text-brand-900">Secrets stay on the server</p>
            <p className="mt-1 text-xs leading-relaxed text-brand-800/80">
              API keys are stored in the local SQLite database and are never returned to this browser. Provider
              requests happen in the backend. Custom endpoints are restricted to approved hosts to prevent SSRF.
              RecruiMate never silently switches to a paid model.
            </p>
          </div>
        </div>
      </div>

      <section className="space-y-4">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h3 className="text-lg font-semibold tracking-tight text-ink-900">AI providers</h3>
            <p className="mt-0.5 text-sm text-ink-500">
              One gateway, seven adapters. Agents never depend on a specific provider.
            </p>
          </div>
          <button className="btn-secondary btn-sm" onClick={refreshHealth} disabled={healthLoading}>
            {healthLoading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Activity className="h-3.5 w-3.5" />}
            {healthLoading ? 'Checking providers…' : 'Check all connections'}
          </button>
        </div>
        <div className="space-y-3">
          {providers.map((provider) => (
            <GatewaySelector
              key={provider.provider}
              provider={provider}
              health={health[provider.provider]}
              onSave={saveProvider}
              onTest={testProvider}
              onLoadModels={loadModels}
              onNotice={setNotice}
            />
          ))}
        </div>
      </section>

      <section className="card card-pad">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-violet-50 text-violet-600">
            <Workflow className="h-4 w-4" />
          </span>
          <div className="flex-1">
            <SectionHeading
              title="Agent routing"
              description="Use the default provider for every agent, or override specific agents. Compatibility and gap analysis are always deterministic."
            />
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              <div>
                <label className="label">Default provider</label>
                <select
                  className="input"
                  value={routing.default_provider}
                  onChange={(e) => setRouting({ ...routing, default_provider: e.target.value })}
                >
                  {providers.map((provider) => (
                    <option key={provider.provider} value={provider.provider}>
                      {provider.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="mt-4 overflow-hidden rounded-xl border border-ink-100">
              <table className="w-full text-left text-xs">
                <thead className="bg-ink-50 text-[10px] uppercase tracking-wide text-ink-500">
                  <tr>
                    <th className="px-3 py-2 font-semibold">Agent</th>
                    <th className="px-3 py-2 font-semibold">Provider override</th>
                    <th className="px-3 py-2 font-semibold">Model override</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-ink-100">
                  {agents.map((agent) => {
                    const override = routing.agent_overrides?.[agent.id] || {}
                    return (
                      <tr key={agent.id}>
                        <td className="px-3 py-2.5">
                          <p className="font-semibold text-ink-800">{agent.label}</p>
                          <p className="text-[10px] text-ink-400">{agent.recommended}</p>
                        </td>
                        <td className="px-3 py-2.5">
                          <select
                            className="input py-1.5 text-xs"
                            value={override.provider || ''}
                            onChange={(e) => setOverride(agent.id, 'provider', e.target.value)}
                          >
                            <option value="">Use default</option>
                            {providers.map((provider) => (
                              <option key={provider.provider} value={provider.provider}>
                                {provider.label}
                              </option>
                            ))}
                          </select>
                        </td>
                        <td className="px-3 py-2.5">
                          <input
                            className="input py-1.5 text-xs"
                            placeholder="Provider default"
                            value={override.model || ''}
                            onChange={(e) => setOverride(agent.id, 'model', e.target.value)}
                          />
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            <div className="mt-3 flex items-center gap-3">
              <button className="btn-primary btn-sm" onClick={saveRouting} disabled={routingSaving}>
                {routingSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                Save routing
              </button>
              <span className="text-[11px] text-ink-400">
                Fallback order: {data?.fallback_order?.join(' → ')}
              </span>
            </div>
          </div>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="card card-pad">
          <SectionHeading title="Local capabilities" />
          <div className="space-y-3">
            <div className="flex items-center justify-between rounded-xl bg-ink-50 px-3 py-2.5">
              <span className="flex items-center gap-2 text-xs font-medium text-ink-700">
                <Cpu className="h-4 w-4 text-brand-500" /> Embeddings
              </span>
              <Badge tone="blue">{data?.embeddings || 'hashed'}</Badge>
            </div>
            <div className="flex items-center justify-between rounded-xl bg-ink-50 px-3 py-2.5">
              <span className="flex items-center gap-2 text-xs font-medium text-ink-700">
                <Database className="h-4 w-4 text-brand-500" /> Data store
              </span>
              <Badge>SQLite · local</Badge>
            </div>
            <div className="flex items-center justify-between rounded-xl bg-ink-50 px-3 py-2.5">
              <span className="flex items-center gap-2 text-xs font-medium text-ink-700">
                <Lock className="h-4 w-4 text-brand-500" /> API mode
              </span>
              <Badge tone="green">{account?.mode || 'trusted-local'}</Badge>
            </div>
          </div>
          <p className="mt-3 text-[11px] leading-relaxed text-ink-400">
            The hashed embedding fallback is deterministic and requires no model download. Install
            <code className="mx-1 rounded bg-ink-100 px-1">sentence-transformers</code>
            for stronger semantic matching; the score weights do not change.
          </p>
        </section>

        <section className="card card-pad">
          <SectionHeading title="Recent provider usage" description="Latency and token usage for this workspace." />
          {usage?.summary?.length ? (
            <div className="space-y-2">
              {usage.summary.map((row) => (
                <div key={row.provider} className="flex items-center justify-between rounded-xl border border-ink-100 px-3 py-2 text-xs">
                  <span className="font-semibold capitalize text-ink-700">{row.provider}</span>
                  <span className="text-ink-500">
                    {row.requests} req · {row.errors} err · {row.avg_latency_ms} ms
                  </span>
                </div>
              ))}
              <p className="pt-1 text-[10px] text-ink-400">
                Last request: {usage.logs?.[0] ? fmtDateTime(usage.logs[0].created_at) : '—'}
              </p>
            </div>
          ) : (
            <p className="text-sm text-ink-400">No provider calls yet. Local heuristics do not create usage logs.</p>
          )}
        </section>
      </div>

      <section className="card border-red-200 p-5">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-red-50 text-red-600">
              <TriangleAlert className="h-4 w-4" />
            </span>
            <div>
              <h3 className="text-sm font-semibold text-ink-900">Delete all data</h3>
              <p className="mt-0.5 max-w-xl text-xs leading-relaxed text-ink-500">
                Removes uploaded resumes, analyses, roadmaps, interview history, provider credentials and usage logs.
                This is permanent and cannot be undone.
              </p>
            </div>
          </div>
          <button className="btn-danger btn-sm shrink-0" onClick={deleteData} disabled={deleting}>
            {deleting ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
            Delete everything
          </button>
        </div>
      </section>

      <p className="flex items-center justify-center gap-1.5 text-center text-[11px] text-ink-400">
        <RefreshCw className="h-3 w-3" /> RecruiMate v1.0 · candidate-side preparation only · no automatic job applications
      </p>
    </div>
  )
}
