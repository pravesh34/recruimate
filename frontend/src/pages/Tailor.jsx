import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  ArrowUpRight,
  CheckCircle2,
  Copy,
  Download,
  FileText,
  Loader2,
  Printer,
  Sparkles,
} from 'lucide-react'
import api, { apiError } from '../services/api'
import { EmptyState, ErrorBanner, LoadingBlock } from '../components/ui'

function useCopy() {
  const [copied, setCopied] = useState('')
  async function copy(label, text) {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(label)
      setTimeout(() => setCopied(''), 1600)
    } catch {
      setCopied('')
    }
  }
  return { copied, copy }
}

function download(blob, filename) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export default function Tailor() {
  const { jobId } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [downloading, setDownloading] = useState('')
  const { copied, copy } = useCopy()

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      setData(await api.tailorForJob(Number(jobId)))
    } catch (e) {
      setError(apiError(e))
    } finally {
      setLoading(false)
    }
  }, [jobId])

  useEffect(() => {
    load()
  }, [load])

  async function exportAs(format, variant = 'asis') {
    setDownloading(variant === 'dream' ? 'dream' : format)
    try {
      const blob = await api.tailorExport(Number(jobId), format, data?.resume_id, variant)
      if (format === 'pdf') {
        const name = variant === 'dream' ? `dream-resume-${jobId}.pdf` : `tailored-resume-${jobId}.pdf`
        download(blob, name)
      } else {
        download(blob, `tailored-${jobId}.${format}`)
      }
    } catch (e) {
      setError(apiError(e))
    } finally {
      setDownloading('')
    }
  }

  if (loading) return <LoadingBlock label="Tailoring your resume…" />
  if (error && !data) {
    return (
      <ErrorBanner
        message={error}
        action={
          <Link to="/jobs" className="btn-secondary btn-sm">
            Back to job search
          </Link>
        }
      />
    )
  }

  const { job, summary, bullets, cover_letter: coverLetter, fit_score: fitScore } = data
  const bulletsText = bullets
    .map((b) => `${b.context}\n${b.text}`)
    .join('\n\n')

  return (
    <div className="space-y-6">
      {error && <ErrorBanner message={error} />}

      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-br from-brand-950 via-brand-900 to-[#1a2452] p-6 text-white shadow-lift sm:p-8">
        <div className="absolute -right-16 -top-24 h-64 w-64 rounded-full bg-brand-500/20 blur-3xl" />
        <div className="relative">
          <p className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.18em] text-brand-200/80">
            <FileText className="h-3.5 w-3.5" /> Tailored application
          </p>
          <h2 className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl">{job?.title}</h2>
          <p className="mt-1 text-sm text-brand-100/75">{job?.company}</p>
          <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full bg-white/10 px-3 py-1 font-semibold">
              Fit score {Math.round(fitScore || 0)}/100
            </span>
            {job?.url && (
              <a
                href={job.url}
                target="_blank"
                rel="noreferrer noopener"
                className="inline-flex items-center gap-1 rounded-full bg-white/10 px-3 py-1 font-semibold text-white"
              >
                Open posting <ArrowUpRight className="h-3 w-3" />
              </a>
            )}
          </div>
        </div>
      </div>

      <div className="card card-pad">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="section-title">Resume bullets, reordered for this role</h3>
            <p className="mt-0.5 text-xs text-ink-500">
              Your real experience — the bullets that prove this job's requirements come first. No content is invented.
            </p>
          </div>
          <button
            type="button"
            onClick={() => copy('bullets', bulletsText)}
            className="btn-secondary btn-sm inline-flex items-center gap-1"
          >
            {copied === 'bullets' ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
            {copied === 'bullets' ? 'Copied' : 'Copy all'}
          </button>
        </div>

        {summary?.matched_skills?.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-1.5">
            {summary.matched_skills.map((s) => (
              <span key={s} className="chip">
                <CheckCircle2 className="mr-1 inline h-3 w-3 text-emerald-500" />
                {s}
              </span>
            ))}
          </div>
        )}
        {summary?.missing_skills?.length > 0 && (
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            <span className="text-[11px] font-semibold text-ink-500">Gaps:</span>
            {summary.missing_skills.map((s) => (
              <span key={s} className="chip-amber">
                {s}
              </span>
            ))}
          </div>
        )}

        <ul className="mt-4 space-y-3">
          {bullets.map((b, i) => (
            <li key={i} className="rounded-2xl border border-ink-100 bg-white p-3.5">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-400">
                {b.context}
              </p>
              <p className="mt-1 text-sm leading-relaxed text-ink-800">{b.text}</p>
              {b.matched_skills?.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {b.matched_skills.map((s) => (
                    <span key={s} className="rounded-md bg-emerald-50 px-1.5 py-0.5 text-[10px] font-bold text-emerald-700">
                      proves {s}
                    </span>
                  ))}
                </div>
              )}
            </li>
          ))}
        </ul>
      </div>

      <div className="card card-pad">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h3 className="section-title">Cover-letter draft</h3>
            <p className="mt-0.5 text-xs text-ink-500">
              Built from your evidence. Edit freely before sending — it's a starting draft.
            </p>
          </div>
          <button
            type="button"
            onClick={() => copy('letter', coverLetter)}
            className="btn-secondary btn-sm inline-flex items-center gap-1"
          >
            {copied === 'letter' ? <CheckCircle2 className="h-3.5 w-3.5 text-emerald-500" /> : <Copy className="h-3.5 w-3.5" />}
            {copied === 'letter' ? 'Copied' : 'Copy'}
          </button>
        </div>
        <pre className="mt-3 whitespace-pre-wrap rounded-2xl bg-ink-50/60 p-4 font-sans text-sm leading-relaxed text-ink-800">
          {coverLetter}
        </pre>
      </div>

      <div className="card card-pad">
        <h3 className="section-title">Export</h3>
        <p className="mt-0.5 text-xs text-ink-500">
          Both PDFs are print-ready — no HTML-to-PDF dance, they download directly.
        </p>

        <div className="mt-4 grid gap-4 md:grid-cols-2">
          <div className="rounded-2xl border border-emerald-200 bg-emerald-50/60 p-4">
            <div className="flex items-center gap-2">
              <FileText className="h-4 w-4 text-emerald-600" />
              <h4 className="text-sm font-bold text-ink-900">My résumé (as-is)</h4>
            </div>
            <p className="mt-1.5 text-xs leading-relaxed text-ink-600">
              Your real profile, reordered to lead with the evidence this job cares about.
              Nothing is invented — safe to send to the recruiter right now.
            </p>
            <button
              type="button"
              onClick={() => exportAs('pdf', 'asis')}
              disabled={Boolean(downloading)}
              className="btn-primary btn-sm mt-3 inline-flex items-center gap-1"
            >
              {downloading === 'asis' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
              Download PDF
            </button>
          </div>

          <div className="rounded-2xl border border-amber-200 bg-amber-50/60 p-4">
            <div className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-amber-600" />
              <h4 className="text-sm font-bold text-ink-900">Dream résumé (target)</h4>
            </div>
            <p className="mt-1.5 text-xs leading-relaxed text-ink-600">
              What your résumé looks like once you close this job's gaps. Each missing skill
              becomes a concrete build goal (◆) with a project idea — a work plan you can
              start today. Clearly labelled; not for sending to recruiters.
            </p>
            <button
              type="button"
              onClick={() => exportAs('pdf', 'dream')}
              disabled={Boolean(downloading)}
              className="btn btn-sm mt-3 inline-flex items-center gap-1 bg-amber-100 text-amber-800 hover:bg-amber-200"
            >
              {downloading === 'dream' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
              Download PDF
            </button>
          </div>
        </div>

        <div className="mt-3 flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => exportAs('html')}
            disabled={Boolean(downloading)}
            className="btn-secondary btn-sm inline-flex items-center gap-1"
          >
            {downloading === 'html' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Printer className="h-3.5 w-3.5" />}
            HTML (print-styled)
          </button>
          <button
            type="button"
            onClick={() => exportAs('md')}
            disabled={Boolean(downloading)}
            className="btn-secondary btn-sm inline-flex items-center gap-1"
          >
            {downloading === 'md' ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Download className="h-3.5 w-3.5" />}
            Markdown
          </button>
        </div>
      </div>
    </div>
  )
}
