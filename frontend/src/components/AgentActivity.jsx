import { CheckCircle2, Cpu, Loader2, XCircle } from 'lucide-react'
import { classNames } from '../services/utils'

const AGENT_LABELS = {
  resume_agent: 'Resume agent',
  job_agent: 'Job agent',
  compatibility_agent: 'Compatibility agent',
  gap_analysis_agent: 'Gap analysis agent',
  interview_agent: 'Interview agent',
  supervisor: 'Supervisor',
}

export default function AgentActivity({ activity = [], providers = {}, engine, errors = [] }) {
  if (!activity.length && !errors.length) return null
  return (
    <div className="card card-pad">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h3 className="section-title">Agent activity</h3>
          <p className="mt-0.5 text-xs text-ink-500">
            {engine ? `Orchestrated with ${engine === 'langgraph' ? 'LangGraph' : 'the async fallback DAG'}.` : 'Supervisor run.'}
          </p>
        </div>
        {engine && (
          <span className="chip-blue">
            <Cpu className="h-3 w-3" /> {engine}
          </span>
        )}
      </div>
      <ol className="space-y-3">
        {activity.map((item, index) => {
          const failed = item.status === 'error'
          return (
            <li key={`${item.agent}-${index}`} className="flex gap-3">
              <div className="flex flex-col items-center">
                <span
                  className={classNames(
                    'flex h-7 w-7 items-center justify-center rounded-full',
                    failed ? 'bg-red-50 text-red-500' : 'bg-emerald-50 text-emerald-600',
                  )}
                >
                  {failed ? <XCircle className="h-3.5 w-3.5" /> : <CheckCircle2 className="h-3.5 w-3.5" />}
                </span>
                {index < activity.length - 1 && <span className="mt-1 h-full w-px flex-1 bg-ink-200" />}
              </div>
              <div className="min-w-0 flex-1 pb-1">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="text-sm font-semibold text-ink-800">
                    {AGENT_LABELS[item.agent] || item.agent}
                  </p>
                  {item.provider && <span className="chip">{item.provider}</span>}
                  {item.duration_ms > 0 && (
                    <span className="text-[11px] text-ink-400">{Math.round(item.duration_ms)} ms</span>
                  )}
                </div>
                {item.detail && <p className="mt-0.5 text-xs text-ink-500">{item.detail}</p>}
              </div>
            </li>
          )
        })}
      </ol>
      {Object.keys(providers || {}).length > 0 && (
        <div className="mt-4 flex flex-wrap gap-1.5 border-t border-ink-100 pt-3">
          {Object.entries(providers).map(([agent, provider]) => (
            <span key={agent} className="chip">
              {AGENT_LABELS[agent] || agent}: {provider}
            </span>
          ))}
        </div>
      )}
      {errors?.length > 0 && (
        <div className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-xs text-amber-700">
          <p className="font-semibold">Fallback notes</p>
          {errors.slice(0, 4).map((error, i) => (
            <p key={i} className="mt-0.5 break-words">{error}</p>
          ))}
        </div>
      )}
    </div>
  )
}
