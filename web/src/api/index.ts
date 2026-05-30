/**
 * API 客户端 — 封装所有后端接口调用
 */
import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

// ─────────────────────────────────────────────
// 知识库
// ─────────────────────────────────────────────

export const kbApi = {
  list: () => api.get('/kb/'),
  get: (kbId: string) => api.get(`/kb/${kbId}`),
  create: (data: {
    name: string; description?: string; domain?: string[]
  }) => api.post('/kb/', data),
  delete: (kbId: string) => api.delete(`/kb/${kbId}`),
}

// ─────────────────────────────────────────────
// 数据采集
// ─────────────────────────────────────────────

export const collectApi = {
  listRaw: (kbId: string, page = 1, pageSize = 20) =>
    api.get(`/collect/${kbId}/raw`, { params: { page, page_size: pageSize } }),
  getRaw: (kbId: string, docId: string) =>
    api.get(`/collect/${kbId}/raw/${docId}`),
  submitRaw: (kbId: string, doc: { title: string; url?: string; content: string; metadata?: object }) =>
    api.post(`/collect/${kbId}/raw`, doc),
  uploadFile: (kbId: string, file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post(`/collect/${kbId}/upload`, form)
  },
  deleteRaw: (kbId: string, docId: string) => api.delete(`/collect/${kbId}/raw/${docId}`),
}

// ─────────────────────────────────────────────
// 处理流水线
// ─────────────────────────────────────────────

export const processApi = {
  run: (kbId: string, params?: { stage?: string; force?: boolean; doc_ids?: string[] }) =>
    api.post(`/process/${kbId}/run`, params || {}),
  getTask: (kbId: string, taskId: string) =>
    api.get(`/process/${kbId}/tasks/${taskId}`),
  streamTask: (kbId: string, taskId: string) =>
    new EventSource(`/api/process/${kbId}/tasks/${taskId}/stream`),
}

// ─────────────────────────────────────────────
// Wiki 内容
// ─────────────────────────────────────────────

export const wikiApi = {
  getPage: (kbId: string, pageType: string, name: string) =>
    api.get(`/wiki/${kbId}/page/${pageType}/${name}`, { responseType: 'text' }),
  getIndex: (kbId: string) =>
    api.get(`/wiki/${kbId}/index`, { responseType: 'text' }),
  listPages: (kbId: string, type: string, page = 1, pageSize = 50) =>
    api.get(`/wiki/${kbId}/pages`, { params: { type, page, page_size: pageSize } }),
  getGraph: (kbId: string) =>
    api.get(`/wiki/${kbId}/graph`),
}

// ─────────────────────────────────────────────
// 搜索问答
// ─────────────────────────────────────────────

export const searchApi = {
  query: (kbId: string, query: string, topK = 5, generateAnswer = true) =>
    api.post(`/search/${kbId}/query`, { query, top_k: topK, generate_answer: generateAnswer }),
  retrieve: (kbId: string, query: string, topK = 5) =>
    api.post(`/search/${kbId}/retrieve`, { query, top_k: topK, generate_answer: false }),
}

export default api
