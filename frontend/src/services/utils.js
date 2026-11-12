export function fmtDate(value, opts = {}) {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '—'
  return date.toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: opts.year === false ? undefined : 'numeric',
  })
}

export function fmtDateTime(value) {
  if (!value) return '—'
  const date = new Date(value)
  return date.toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}

export function scoreTone(score) {
  if (score >= 75) return { text: 'text-emerald-600', bg: 'bg-emerald-50', ring: '#12b981', label: 'Strong' }
  if (score >= 55) return { text: 'text-brand-600', bg: 'bg-brand-50', ring: '#2559e8', label: 'Moderate' }
  if (score >= 35) return { text: 'text-amber-600', bg: 'bg-amber-50', ring: '#f59e0b', label: 'Stretch' }
  return { text: 'text-red-600', bg: 'bg-red-50', ring: '#ef4444', label: 'Needs work' }
}

export function initials(name = '') {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((part) => part[0]?.toUpperCase())
      .join('') || 'RM'
  )
}

export function classNames(...values) {
  return values.filter(Boolean).join(' ')
}

export function truncate(text = '', length = 140) {
  return text.length > length ? `${text.slice(0, length).trim()}…` : text
}

export function prettySkill(skill = '') {
  return skill.replace(/\b\w/g, (c) => c.toUpperCase())
}

export const QUESTION_TYPE_META = {
  technical: { label: 'Technical', className: 'chip-blue' },
  project: { label: 'Project', className: 'chip-violet' },
  hr: { label: 'HR', className: 'chip-green' },
  behavioural: { label: 'Behavioural', className: 'chip-amber' },
  problem_solving: { label: 'Problem solving', className: 'chip-red' },
}

export const SCORE_DIMENSIONS = [
  { key: 'technical_accuracy', label: 'Technical accuracy' },
  { key: 'conceptual_understanding', label: 'Conceptual depth' },
  { key: 'communication', label: 'Communication' },
  { key: 'problem_solving', label: 'Problem solving' },
  { key: 'relevance', label: 'Relevance' },
  { key: 'completeness', label: 'Completeness' },
]
