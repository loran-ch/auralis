import { request, upload } from './http'

const query = (params = {}) => {
  const entries = Object.entries(params).filter(([, value]) => value !== '' && value !== null && value !== undefined)
  return entries.length ? `?${entries.map(([key, value]) => `${encodeURIComponent(key)}=${encodeURIComponent(value)}`).join('&')}` : ''
}

export const authApi = {
  login: (account, password) => request('/api/auth/login', { method: 'POST', auth: false, data: { account, password } }),
  sendCode: (target) => request('/api/auth/send-code', { method: 'POST', auth: false, data: { target, scene: 'register' } }),
  register: (data) => request('/api/auth/register', { method: 'POST', auth: false, data }),
  me: () => request('/api/auth/me'),
  stats: () => request('/api/auth/stats'),
  updateProfile: (data) => request('/api/auth/profile', { method: 'PUT', data }),
  changePassword: (data) => request('/api/auth/password', { method: 'PUT', data }),
  uploadAvatar: (filePath) => upload('/api/auth/avatar', filePath),
  logout: () => request('/api/auth/logout', { method: 'POST', retry: false }),
  logoutAll: () => request('/api/auth/logout-all', { method: 'POST', retry: false }),
}

export const preferenceApi = {
  languages: () => request('/api/languages', { auth: false }),
  settings: () => request('/api/settings'),
  saveSettings: (data) => request('/api/settings', { method: 'PUT', data }),
  schedules: (includeInactive = false) => request(`/api/schedules${query({ include_inactive: includeInactive })}`),
  createSchedule: (data) => request('/api/schedules', { method: 'POST', data }),
  updateSchedule: (id, data) => request(`/api/schedules/${id}`, { method: 'PUT', data }),
  removeSchedule: (id) => request(`/api/schedules/${id}`, { method: 'DELETE' }),
}

export const lectureApi = {
  start: (data) => request('/api/lectures/start', { method: 'POST', data }),
  active: () => request('/api/lectures/active'),
  pause: (id) => request(`/api/lectures/${id}/pause`, { method: 'POST' }),
  resume: (id) => request(`/api/lectures/${id}/resume`, { method: 'POST' }),
  stop: (id) => request(`/api/lectures/${id}/stop`, { method: 'POST' }),
  rename: (id, courseName) => request(`/api/lectures/${id}/rename`, { method: 'PUT', data: { course_name: courseName } }),
  update: (id, data) => request(`/api/lectures/${id}`, { method: 'PATCH', data }),
  list: (params) => request(`/api/lectures${query(params)}`),
  detail: (id) => request(`/api/lectures/${id}`),
  transcriptions: (id, limit = 200) => request(`/api/lectures/${id}/transcriptions${query({ limit })}`),
  demoTranscribe: (id) => request(`/api/lectures/${id}/transcribe`, { method: 'POST' }),
  saveText: (id, data) => request(`/api/lectures/${id}/transcribe/text`, { method: 'POST', data }),
  transcribeAudio: (id, filePath, append = false) => upload(
    `/api/lectures/${id}/transcribe/audio`,
    filePath,
    { append: append ? 'true' : 'false' },
  ),
  uploadAudio: (id, filePath, append = false) => upload(`/api/lectures/${id}/audio`, filePath, { append: append ? 'true' : 'false' }),
  remove: (id) => request(`/api/lectures/${id}`, { method: 'DELETE' }),
  batchRemove: (ids) => request('/api/lectures/batch-delete', { method: 'POST', data: { ids } }),
  translate: (data) => request('/api/translate', { method: 'POST', data }),
}

export const bookmarkApi = {
  list: (tag = '') => request(`/api/bookmarks${query({ tag, limit: 100 })}`),
  add: (data) => request('/api/bookmarks', { method: 'POST', data }),
  update: (id, data) => request(`/api/bookmarks/${id}`, { method: 'PATCH', data }),
  remove: (id) => request(`/api/bookmarks/${id}`, { method: 'DELETE' }),
  removeByTranscription: (id) => request(`/api/bookmarks/by-transcription/${id}`, { method: 'DELETE' }),
}

export const adminApi = {
  dashboard: () => request('/api/admin/dashboard'),
  users: (params) => request(`/api/admin/users${query(params)}`),
  updateUserStatus: (id, status) => request(`/api/admin/users/${id}/status`, { method: 'PATCH', data: { status } }),
  updateUserRole: (id, role) => request(`/api/admin/users/${id}/role`, { method: 'PATCH', data: { role } }),
  removeUser: (id) => request(`/api/admin/users/${id}`, { method: 'DELETE' }),
  lectures: (params) => request(`/api/admin/lectures${query(params)}`),
  removeLecture: (id) => request(`/api/admin/lectures/${id}`, { method: 'DELETE' }),
  auditLogs: (params) => request(`/api/admin/audit-logs${query(params)}`),
}
