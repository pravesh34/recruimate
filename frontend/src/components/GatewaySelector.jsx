import { useEffect, useState } from 'react'
import {
  Activity,
  Check,
  ChevronDown,
  Eye,
  EyeOff,
  Globe2,
  KeyRound,
  Loader2,
  Save,
  Server,
  Sparkles,
  TriangleAlert,
} from 'lucide-react'
import { classNames } from '../services/utils'
import { Badge } from './ui'

const ICONS = {
  openrouter: Globe2,
  groq: Sparkles,
  gemini: Sparkles,
  opencode: Server,
  ollama: Server,
  custom: Globe2,
  heuristic: Activity,
}

export default function GatewaySelector({ provider, health, onSave, onTest, onLoadModels, onNotice }) {
  const [open, setOpen] = useState(provider.provider === 'openrouter')
  const [draft, setDraft] = useState(provider)
  const [models, setModels] = useState([])
  const [saving, setSaving] = useState(false)
  const [testing, setTesting] = useState(false)
  const [loadingModels, setLoadingModels] = useState(false)
  const [showKey, setShowKey] = useState(false)
  const [testResult, setTestResult] = useState(null)

  useEffect(() => {
    setDraft(provider)
  }, [provider])

  const Icon = ICONS[provider.provider] || Server
  const isHeuristic = provider.provider === 'heuristic'
  const healthy = health?.healthy
  const statusLabel = isHeuristic
    ? 'Always available'
    : !provider.configured
      ? 'Not configured'
      : healthy === undefined
        ? 'Not tested'
        : healthy
          ? 'Healthy'
          : 'Unreachable'

  const statusTone = isHeuristic || healthy ? 'green' : provider.configured ? 'amber' : 'ink'

  async function save() {
    setSaving(true)
    try {
      await onSave({
        provider: provider.provider,
        enabled: draft.enabled,
        model: draft.model,
        base_url: draft.base_url,
        temperature: Number(draft.temperature),
        max_tokens: Number(draft.max_tokens),
        is_paid: Boolean(draft.is_paid),
        api_key: draft.api_key || undefined,
      })
      setDraft((current) => ({ ...current, api_key: '' }))
    } finally {
      setSaving(false)
    }
  }

  async function test() {
    setTesting(true)
    setTestResult(null)
    try {
      const result = await onTest(provider.provider, draft.model)
      setTestResult(result)
    } finally {
      setTesting(false)
    }
  }

  async function loadModels() {
    setLoadingModels(true)
    try {
      const result = await onLoadModels(provider.provider)
      setModels(result || [])
      if (result?.length === 0) onNotice?.('No models were returned. Check credentials or the base URL.')
    } finally {
      setLoadingModels(false)
    }
  }

  return (
    <div className={classNames('card overflow-hidden transition', draft.enabled && 'ring-1 ring-brand-200')}>
      <button className="flex w-full items-center gap-3 px-5 py-4 text-left" onClick={() => setOpen(!open)}>
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
          <Icon className="h-5 w-5" />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm font-semibold text-ink-900">{provider.label}</p>
            <Badge tone={statusTone}>
              <span className={classNames('h-1.5 w-1.5 rounded-full', isHeuristic || healthy ? 'bg-emerald-500' : provider.configured ? 'bg-amber-500' : 'bg-ink-300')} />
              {statusLabel}
            </Badge>
            {provider.is_paid && <Badge tone="red">Paid</Badge>}
            {draft.enabled && <Badge tone="blue">Enabled</Badge>}
          </div>
          <p className="mt-0.5 truncate text-[11px] text-ink-500">
            {provider.model || 'No model selected'} {provider.base_url ? `· ${provider.base_url}` : ''}
          </p>
        </div>
        <ChevronDown className={classNames('h-4 w-4 shrink-0 text-ink-400 transition', open && 'rotate-180')} />
      </button>

      {open && (
        <div className="border-t border-ink-100 px-5 py-4">
          <p className="mb-4 text-xs leading-relaxed text-ink-500">{provider.note}</p>

          {isHeuristic ? (
            <div className="rounded-xl bg-emerald-50 px-4 py-3 text-xs leading-relaxed text-emerald-800">
              Local heuristics run offline: resume parsing, weighted compatibility scoring, roadmap generation and
              rule-based interview evaluation. No data leaves this device. Configure a provider to add LLM reasoning.
            </div>
          ) : (
            <div className="space-y-4">
              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className="label flex items-center gap-1.5">
                    <KeyRound className="h-3 w-3" /> API key / password
                  </label>
                  <div className="relative">
                    <input
                      className="input pr-10"
                      type={showKey ? 'text' : 'password'}
                      placeholder={provider.api_key_set ? `${provider.api_key_hint} stored — enter to replace` : 'Paste a key'}
                      value={draft.api_key || ''}
                      onChange={(e) => setDraft({ ...draft, api_key: e.target.value })}
                      autoComplete="off"
                    />
                    <button
                      type="button"
                      onClick={() => setShowKey(!showKey)}
                      className="absolute right-2.5 top-1/2 -translate-y-1/2 text-ink-400 hover:text-ink-600"
                      aria-label={showKey ? 'Hide key' : 'Show key'}
                    >
                      {showKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  </div>
                </div>
                <div>
                  <label className="label">{provider.provider === 'opencode' ? 'Session URL' : 'Base URL'}</label>
                  <input
                    className="input"
                    value={draft.base_url || ''}
                    onChange={(e) => setDraft({ ...draft, base_url: e.target.value })}
                    placeholder="https://…"
                  />
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-2">
                <div>
                  <label className="label">Model</label>
                  <div className="flex gap-2">
                    <input
                      className="input"
                      value={draft.model || ''}
                      onChange={(e) => setDraft({ ...draft, model: e.target.value })}
                      placeholder={provider.provider === 'opencode' ? 'providerID/modelID' : 'model id'}
                      list={`models-${provider.provider}`}
                    />
                    <datalist id={`models-${provider.provider}`}>
                      {models.map((model) => (
                        <option key={model} value={model} />
                      ))}
                    </datalist>
                    <button className="btn-secondary btn-sm shrink-0" onClick={loadModels} disabled={loadingModels}>
                      {loadingModels ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : 'List'}
                    </button>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="label">Temperature</label>
                    <input
                      type="number"
                      min="0"
                      max="2"
                      step="0.1"
                      className="input"
                      value={draft.temperature ?? 0.3}
                      onChange={(e) => setDraft({ ...draft, temperature: e.target.value })}
                    />
                  </div>
                  <div>
                    <label className="label">Max tokens</label>
                    <input
                      type="number"
                      min="64"
                      max="32000"
                      step="64"
                      className="input"
                      value={draft.max_tokens ?? 1500}
                      onChange={(e) => setDraft({ ...draft, max_tokens: e.target.value })}
                    />
                  </div>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-4">
                <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-ink-600">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-brand-300"
                    checked={Boolean(draft.enabled)}
                    onChange={(e) => setDraft({ ...draft, enabled: e.target.checked })}
                  />
                  Enable this provider
                </label>
                <label className="flex cursor-pointer items-center gap-2 text-xs font-medium text-ink-600">
                  <input
                    type="checkbox"
                    className="h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-brand-300"
                    checked={Boolean(draft.is_paid)}
                    onChange={(e) => setDraft({ ...draft, is_paid: e.target.checked })}
                  />
                  Mark as paid (blocks silent fallback)
                </label>
              </div>

              {provider.provider === 'opencode' && (
                <div className="flex gap-2 rounded-xl bg-amber-50 px-3 py-2 text-[11px] leading-relaxed text-amber-800">
                  <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
                  Use a dedicated restricted OpenCode server. This adapter only creates a temporary session, sends one
                  prompt and deletes the session — but the runtime may still have tools enabled server-side.
                </div>
              )}

              <div className="flex flex-wrap items-center gap-2">
                <button className="btn-primary btn-sm" onClick={save} disabled={saving}>
                  {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Save className="h-3.5 w-3.5" />}
                  Save configuration
                </button>
                <button className="btn-secondary btn-sm" onClick={test} disabled={testing || !provider.configured}>
                  {testing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Activity className="h-3.5 w-3.5" />}
                  Test connection
                </button>
                {!provider.configured && (
                  <span className="text-[11px] text-ink-400">Add credentials and save before testing.</span>
                )}
              </div>

              {(testResult || health) && (
                <div
                  className={classNames(
                    'rounded-xl px-3 py-2 text-[11px] leading-relaxed',
                    testResult?.healthy ?? health?.healthy
                      ? 'bg-emerald-50 text-emerald-800'
                      : 'bg-red-50 text-red-700',
                  )}
                >
                  <p className="font-semibold">
                    {(testResult?.healthy ?? health?.healthy) ? (
                      <span className="flex items-center gap-1"><Check className="h-3 w-3" /> Connection healthy</span>
                    ) : (
                      <span className="flex items-center gap-1"><TriangleAlert className="h-3 w-3" /> Connection issue</span>
                    )}
                  </p>
                  <p className="mt-0.5 break-words">{testResult?.detail || health?.detail || 'No detail.'}</p>
                  {(testResult?.reply || health?.latency_ms) && (
                    <p className="mt-0.5 text-[10px] opacity-80">
                      {testResult?.reply ? `Reply: ${testResult.reply}` : `Latency: ${health.latency_ms} ms`}
                    </p>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
