import axios from 'axios'

const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((config) => {
  const uid = localStorage.getItem('uid')
  if (uid) config.headers['X-UID'] = uid
  return config
})

api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('uid')
      localStorage.removeItem('uname')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  },
)

// ---- 鉴权 ----
export const register = (uname, password) => api.post('/register', { uname, password })
export const login = (uname, password) => api.post('/login', { uname, password })

// ---- 历史 ----
export const getSessions = () => api.get('/sessions')
export const getSession = (id) => api.get(`/sessions/${id}`)
export const deleteSession = (id) => api.delete(`/sessions/${id}`)

// ---- 文件 ----
export const uploadVideo = (file, onProgress) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/upload/video', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: onProgress,
  })
}
export const listVideos = () => api.get('/videos')

// ---- RAG 文档 ----
export const uploadDocument = (file, onProgress) => {
  const form = new FormData()
  form.append('file', file)
  return api.post('/rag/upload', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: onProgress,
  })
}
export const listDocuments = () => api.get('/rag/documents')
export const deleteDocument = (sourceName) => api.delete(`/rag/documents/${encodeURIComponent(sourceName)}`)
export const clearDocuments = () => api.delete('/rag/documents')

// ---- 健康检查 ----
export const healthCheck = () => api.get('/health')

export default api
