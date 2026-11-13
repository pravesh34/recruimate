import axios from 'axios'

const client = axios.create({
  baseURL: '/api',
  timeout: 180000,
  headers: { 'Content-Type': 'application/json' },
})

const token = import.meta.env.VITE_API_TOKEN
if (token) client.defaults.headers.common.Authorization = `Bearer ${token}`

// --- Token store -----------------------------------------------------------
const ACCESS_KEY = 'recruimate.access_token'
const REFRESH_KEY = 'recruimate.refresh_token'

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS_KEY) || ''
  },
  get refresh() {
    return localStorage.getItem(REFRESH_KEY) || ''
  },
  set({ access_token, refresh_token }) {
    if (access_token) localStorage.setItem(ACCESS_KEY, access_token)
    if (refresh_token) localStorage.setItem(REFRESH_KEY, refresh_token)
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

// Attach the bearer token to every request.
client.interceptors.request.use((config) => {
  const access = tokens.access
  if (access) {
    config.headers = config.headers || {}
    config.headers.Authorization = `Bearer ${access}`
  }
  return config
})

// On 401, try one silent refresh before giving up.
let refreshing = null
client.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config
    if (error?.response?.status !== 401 || original?._retried || !tokens.refresh) {
      return Promise.reject(error)
    }
    original._retried = true
    try {
      refreshing =
        refreshing ||
        client.post('/auth/refresh', { refresh_token: tokens.refresh }).then((r) => {
          refreshing = null
          tokens.set(r.data)
          return r.data.access_token
        })
      const access = await refreshing
      original.headers = original.headers || {}
      original.headers.Authorization = `Bearer ${access}`
      return client(original)
    } catch (e) {
      tokens.clear()
      return Promise.reject(e)
    }
  },
)

export function apiError(error) {
  const detail = error?.response?.data?.detail
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg || d.message || JSON.stringify(d)).join(', ')
  }
  if (typeof detail === 'string') return detail
  return error?.message || 'Something went wrong. Please try again.'
}

export const api = {
  health: () => client.get('/health').then((r) => r.data),

  // Auth
  authStatus: () => client.get('/auth/status').then((r) => r.data),
  register: (payload) => client.post('/auth/register', payload).then((r) => r.data),
  login: (payload) => client.post('/auth/login', payload).then((r) => r.data),
  logout: () => {
    const refresh = tokens.refresh
    tokens.clear()
    return refresh
      ? client.post('/auth/logout', { refresh_token: refresh }).catch(() => {})
      : Promise.resolve()
  },
  me: () => client.get('/auth/me').then((r) => r.data),
  listSessions: () => client.get('/auth/sessions').then((r) => r.data),
  revokeSession: (id) => client.post(`/auth/sessions/${id}/revoke`).then((r) => r.data),
  changePassword: (payload) => client.post('/auth/change-password', payload).then((r) => r.data),

  // Resume
  uploadResume: (file, onProgress) => {
    const form = new FormData()
    form.append('file', file)
    return client
      .post('/resume/upload', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
        onUploadProgress: (e) => {
          if (onProgress && e.total) onProgress(Math.round((e.loaded / e.total) * 100))
        },
      })
      .then((r) => r.data)
  },
  getResume: () => client.get('/resume/profile').then((r) => r.data),
  getResumeById: (id) => client.get(`/resume/profile/${id}`).then((r) => r.data),
  listResumes: () => client.get('/resume').then((r) => r.data),
  deleteResume: (id) => client.delete(`/resume/${id}`).then((r) => r.data),

  // Jobs
  analyzeJob: (payload) => client.post('/jobs/analyze', payload).then((r) => r.data),
  listJobs: () => client.get('/jobs').then((r) => r.data),
  getJob: (id) => client.get(`/jobs/${id}`).then((r) => r.data),
  deleteJob: (id) => client.delete(`/jobs/${id}`).then((r) => r.data),

  // Job search: rank every posting by compatibility with a resume
  matchResumeToJobs: (resumeId) =>
    client
      .get('/jobs/match-resume', { params: resumeId ? { resume_id: resumeId } : {} })
      .then((r) => r.data),

  // Compatibility / analysis
  analyzeCompatibility: (payload) => client.post('/compatibility/analyze', payload).then((r) => r.data),
  runAnalysis: (payload) => client.post('/analysis/run', payload).then((r) => r.data),
  listCompatibility: () => client.get('/compatibility').then((r) => r.data),
  getCompatibility: (id) => client.get(`/compatibility/${id}`).then((r) => r.data),

  // Skill gaps
  generateGap: (compatibilityId) =>
    client.post('/skill-gaps/generate', { compatibility_id: compatibilityId }).then((r) => r.data),
  listGaps: () => client.get('/skill-gaps').then((r) => r.data),
  getGap: (id) => client.get(`/skill-gaps/${id}`).then((r) => r.data),
  updateTask: (taskId, completed) =>
    client.patch(`/skill-gaps/tasks/${taskId}`, { completed }).then((r) => r.data),

  // Interviews
  interviewPrep: (payload) => client.post('/interviews/prep', payload).then((r) => r.data),
  createInterview: (payload) => client.post('/interviews', payload).then((r) => r.data),
  answerInterview: (id, answer) => client.post(`/interviews/${id}/answer`, { answer }).then((r) => r.data),
  completeInterview: (id) => client.post(`/interviews/${id}/complete`).then((r) => r.data),
  getInterview: (id) => client.get(`/interviews/${id}`).then((r) => r.data),
  listInterviews: () => client.get('/interviews').then((r) => r.data),
  deleteInterview: (id) => client.delete(`/interviews/${id}`).then((r) => r.data),

  // Dashboard
  getDashboard: () => client.get('/dashboard').then((r) => r.data),
  getAnalytics: () => client.get('/analytics').then((r) => r.data),

  // Providers
  getProviders: () => client.get('/providers').then((r) => r.data),
  getProviderHealth: () => client.get('/providers/health').then((r) => r.data),
  testProvider: (provider, model) =>
    client.post('/providers/test', { provider, model }).then((r) => r.data),
  getProviderModels: (provider) =>
    client.get('/providers/models', { params: { provider } }).then((r) => r.data),
  updateProvider: (payload) => client.put('/providers/configuration', payload).then((r) => r.data),
  updateRouting: (payload) => client.put('/providers/routing', payload).then((r) => r.data),
  getUsage: () => client.get('/providers/usage').then((r) => r.data),

  // Account
  getAccount: () => client.get('/account').then((r) => r.data),
  deleteAllData: () => client.delete('/account/data').then((r) => r.data),
}

export default api
