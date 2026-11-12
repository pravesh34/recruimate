import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  PolarAngleAxis,
  PolarGrid,
  Radar,
  RadarChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'

const AXIS = { fontSize: 11, fill: '#8b94ae' }
const TOOLTIP_STYLE = {
  borderRadius: 12,
  border: '1px solid #d9dce8',
  boxShadow: '0 12px 32px -12px rgba(13,27,75,0.28)',
  fontSize: 12,
}

export function CategoryBars({ categories = [] }) {
  const data = categories.map((c) => ({ name: c.name.replace('Relevant ', ''), score: Math.round(c.score) }))
  const color = (value) => (value >= 65 ? '#12b981' : value >= 40 ? '#2559e8' : '#f59e0b')
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 12, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#eceef5" />
        <XAxis type="number" domain={[0, 100]} tick={AXIS} axisLine={false} tickLine={false} />
        <YAxis dataKey="name" type="category" width={105} tick={AXIS} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [`${v}/100`, 'Score']} />
        <Bar dataKey="score" radius={[0, 8, 8, 0]} barSize={16}>
          {data.map((entry, index) => (
            <Cell key={index} fill={color(entry.score)} />
          ))}
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  )
}

export function WeakSkillsChart({ skills = [] }) {
  const data = skills.slice(0, 8).map((s) => ({
    name: s.skill.length > 18 ? `${s.skill.slice(0, 16)}…` : s.skill,
    missing: s.missing || 0,
    partial: s.partial || 0,
  }))
  return (
    <ResponsiveContainer width="100%" height={260}>
      <BarChart data={data} layout="vertical" margin={{ left: 8, right: 16, top: 4, bottom: 4 }}>
        <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#eceef5" />
        <XAxis type="number" allowDecimals={false} tick={AXIS} axisLine={false} tickLine={false} />
        <YAxis dataKey="name" type="category" width={110} tick={AXIS} axisLine={false} tickLine={false} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Bar dataKey="missing" stackId="a" fill="#ef4444" radius={[0, 0, 0, 0]} barSize={14} name="Missing" />
        <Bar dataKey="partial" stackId="a" fill="#f59e0b" radius={[0, 6, 6, 0]} barSize={14} name="Partial" />
      </BarChart>
    </ResponsiveContainer>
  )
}

export function ScoreTrend({ data = [], dataKey = 'score', height = 240 }) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <LineChart data={data} margin={{ left: 0, right: 12, top: 8, bottom: 0 }}>
        <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#eceef5" />
        <XAxis dataKey="label" tick={AXIS} axisLine={false} tickLine={false} />
        <YAxis domain={[0, 100]} tick={AXIS} axisLine={false} tickLine={false} width={28} />
        <Tooltip contentStyle={TOOLTIP_STYLE} />
        <Line
          type="monotone"
          dataKey={dataKey}
          stroke="#2559e8"
          strokeWidth={2.5}
          dot={{ r: 3, fill: '#2559e8' }}
          activeDot={{ r: 5 }}
        />
      </LineChart>
    </ResponsiveContainer>
  )
}

export function CategoryRadar({ evaluations = [] }) {
  const dims = [
    ['technical_accuracy', 'Technical'],
    ['conceptual_understanding', 'Concepts'],
    ['communication', 'Communication'],
    ['problem_solving', 'Problem solving'],
    ['relevance', 'Relevance'],
    ['completeness', 'Completeness'],
  ]
  const data = dims.map(([key, label]) => {
    const values = evaluations.map((e) => Number(e.scores?.[key] ?? 0)).filter((n) => !Number.isNaN(n))
    const avg = values.length ? values.reduce((a, b) => a + b, 0) / values.length : 0
    return { dimension: label, score: Math.round(avg) }
  })
  return (
    <ResponsiveContainer width="100%" height={270}>
      <RadarChart data={data} outerRadius="72%">
        <PolarGrid stroke="#e3e8f2" />
        <PolarAngleAxis dataKey="dimension" tick={{ fontSize: 10, fill: '#6b748f' }} />
        <Radar dataKey="score" stroke="#7c5cfc" fill="#7c5cfc" fillOpacity={0.22} />
        <Tooltip contentStyle={TOOLTIP_STYLE} formatter={(v) => [`${v}/100`, 'Average']} />
      </RadarChart>
    </ResponsiveContainer>
  )
}
