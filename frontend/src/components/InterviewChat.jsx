import { useEffect, useRef, useState } from 'react'
import { Bot, CornerDownLeft, Loader2, Send, Sparkles, User } from 'lucide-react'
import { classNames, fmtDateTime, scoreTone } from '../services/utils'
import { SCORE_DIMENSIONS } from '../services/utils'
import { ProgressBar } from './ui'

export default function InterviewChat({ session, onAnswer, busy, evaluation }) {
  const [answer, setAnswer] = useState('')
  const scrollRef = useRef(null)
  const messages = session?.messages || []
  const active = session?.status === 'active'

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [messages.length, busy])

  useEffect(() => {
    setAnswer('')
  }, [session?.current_question?.id, session?.current_question?.question, session?.status])

  function submit() {
    if (!answer.trim() || busy || !active) return
    onAnswer(answer.trim())
    setAnswer('')
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-ink-100 px-5 py-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-wider text-ink-400">Mock interview</p>
            <h3 className="text-sm font-semibold text-ink-900">{session?.role || 'Target role'}</h3>
          </div>
          <div className="flex items-center gap-2 text-xs text-ink-500">
            <Sparkles className="h-3.5 w-3.5 text-brand-500" />
            {session?.provider || 'heuristic'}
            <span className="chip">{session?.progress?.answered || 0}/{session?.progress?.total || 0} answered</span>
          </div>
        </div>
        <ProgressBar value={session?.progress?.percent || 0} className="mt-3" />
      </div>

      <div ref={scrollRef} className="scroll-thin flex-1 space-y-4 overflow-y-auto px-5 py-5" style={{ maxHeight: 520 }}>
        {messages.map((message) => {
          if (message.role === 'system') return null
          const isAssistant = message.role === 'assistant'
          const isQuestion = message.meta?.kind === 'question' || message.meta?.kind === 'follow_up'
          return (
            <div key={message.id || `${message.role}-${message.content.slice(0, 20)}`} className={classNames('flex gap-2.5', !isAssistant && 'flex-row-reverse')}>
              <span
                className={classNames(
                  'flex h-8 w-8 shrink-0 items-center justify-center rounded-full',
                  isAssistant ? 'bg-brand-100 text-brand-600' : 'bg-ink-800 text-white',
                )}
              >
                {isAssistant ? <Bot className="h-4 w-4" /> : <User className="h-4 w-4" />}
              </span>
              <div className={classNames('max-w-[85%]', !isAssistant && 'text-right')}>
                <div
                  className={classNames(
                    'inline-block rounded-2xl px-4 py-2.5 text-left text-sm leading-relaxed',
                    isAssistant
                      ? isQuestion
                        ? 'rounded-tl-md border border-brand-100 bg-brand-50/70 font-medium text-ink-800'
                        : 'rounded-tl-md bg-ink-50 text-ink-600'
                      : 'rounded-tr-md bg-ink-800 text-white',
                  )}
                >
                  {message.content}
                </div>
                <p className="mt-1 text-[10px] text-ink-400">
                  {fmtDateTime(message.created_at)}
                  {message.meta?.kind === 'follow_up' && ' · follow-up'}
                </p>
              </div>
            </div>
          )
        })}
        {busy && (
          <div className="flex items-center gap-2 text-xs text-ink-400">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Evaluating your answer…
          </div>
        )}
      </div>

      {evaluation && (
        <div className="border-t border-ink-100 bg-ink-50/60 px-5 py-4">
          <div className="flex items-center justify-between">
            <p className="text-xs font-semibold text-ink-700">Answer feedback</p>
            <span className={classNames('text-sm font-bold', scoreTone(evaluation.overall).text)}>
              {Math.round(evaluation.overall)}/100
            </span>
          </div>
          <p className="mt-1 text-xs leading-relaxed text-ink-600">{evaluation.feedback}</p>
          <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-3">
            {SCORE_DIMENSIONS.map((dim) => (
              <div key={dim.key} className="rounded-lg bg-white px-2.5 py-2">
                <p className="text-[10px] text-ink-400">{dim.label}</p>
                <p className="text-xs font-semibold text-ink-700">{Math.round(evaluation[dim.key] || 0)}</p>
              </div>
            ))}
          </div>
          {evaluation.suggestions?.length > 0 && (
            <ul className="mt-2 space-y-1">
              {evaluation.suggestions.slice(0, 3).map((tip, i) => (
                <li key={i} className="text-[11px] leading-relaxed text-ink-500">• {tip}</li>
              ))}
            </ul>
          )}
        </div>
      )}

      {active ? (
        <div className="border-t border-ink-100 p-4">
          <textarea
            className="input min-h-[96px] resize-y"
            placeholder="Type your answer as you would say it in an interview…"
            value={answer}
            onChange={(e) => setAnswer(e.target.value)}
            onKeyDown={(e) => {
              if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') submit()
            }}
            disabled={busy}
          />
          <div className="mt-2 flex items-center justify-between gap-2">
            <span className="flex items-center gap-1 text-[10px] text-ink-400">
              <CornerDownLeft className="h-3 w-3" /> Ctrl/⌘ + Enter to send
            </span>
            <button className="btn-primary" onClick={submit} disabled={busy || !answer.trim()}>
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
              Send answer
            </button>
          </div>
        </div>
      ) : (
        <div className="border-t border-ink-100 px-5 py-4 text-center text-xs text-ink-500">
          This interview is complete. Open the report for detailed feedback.
        </div>
      )}
    </div>
  )
}
