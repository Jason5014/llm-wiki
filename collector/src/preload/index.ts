/**
 * Preload 脚本 — 安全地向渲染进程暴露 Node.js/Electron API
 * 通过 contextBridge 避免直接暴露 Node.js API
 */
import { contextBridge, ipcRenderer } from 'electron'
import { electronAPI } from '@electron-toolkit/preload'

// ─────────────────────────────────────────────
// 类型定义（渲染进程可见）
// ─────────────────────────────────────────────

export interface CrawlTask {
  id: string
  kb_id: string
  url: string
  status: 'pending' | 'running' | 'done' | 'failed'
  priority: number
  created_at: string
  updated_at?: string
  error?: string
  doc_id?: string
}

export interface CollectorAPI {
  // 设置
  getSettings: () => Promise<{ apiBaseUrl: string; currentKbId: string }>
  setSettings: (settings: Record<string, unknown>) => Promise<boolean>

  // 知识库 API
  listKbs: () => Promise<unknown[]>
  createKb: (params: { name: string; domain?: string[]; description?: string }) => Promise<unknown>
  submitDoc: (kbId: string, doc: unknown) => Promise<{ doc_id: string; saved: boolean }>
  batchSubmit: (kbId: string, docs: unknown[]) => Promise<{ saved: number; doc_ids: string[] }>
  uploadFile: (kbId: string, filePath: string) => Promise<{ doc_id: string; saved: boolean; title: string }>

  // 内容提取
  extractContent: (webContentsId: number) => Promise<{
    title: string
    content: string
    url: string
    metadata: Record<string, unknown>
  }>

  // 文件对话框
  openFilesDialog: () => Promise<string[]>

  // Cookie 管理
  getAllCookies: (domain?: string) => Promise<unknown[]>
  clearCookies: (domain?: string) => Promise<boolean>

  // 采集任务队列（自动化）
  getCrawlTasks: (params: { status?: string; kbId?: string; limit?: number }) => Promise<{
    tasks: CrawlTask[]
    total: number
  }>
  updateCrawlTask: (params: {
    taskId: string
    status: string
    error?: string
    docId?: string
  }) => Promise<{ updated: boolean }>
}

// ─────────────────────────────────────────────
// 暴露 API 到渲染进程
// ─────────────────────────────────────────────

const collectorAPI: CollectorAPI = {
  getSettings: () => ipcRenderer.invoke('settings:get'),
  setSettings: (settings) => ipcRenderer.invoke('settings:set', settings),

  listKbs: () => ipcRenderer.invoke('api:listKbs'),
  createKb: (params) => ipcRenderer.invoke('api:createKb', params),
  submitDoc: (kbId, doc) => ipcRenderer.invoke('api:submitDoc', { kbId, doc }),
  batchSubmit: (kbId, docs) => ipcRenderer.invoke('api:batchSubmit', { kbId, docs }),
  uploadFile: (kbId, filePath) => ipcRenderer.invoke('api:uploadFile', { kbId, filePath }),

  extractContent: (webContentsId) =>
    ipcRenderer.invoke('browser:extractContent', { webContentsId }),

  openFilesDialog: () => ipcRenderer.invoke('dialog:openFiles'),

  getAllCookies: (domain?) => ipcRenderer.invoke('cookies:getAll', domain),
  clearCookies: (domain?) => ipcRenderer.invoke('cookies:clear', domain),

  getCrawlTasks: (params) => ipcRenderer.invoke('api:getCrawlTasks', params),
  updateCrawlTask: (params) => ipcRenderer.invoke('api:updateCrawlTask', params),
}

// 暴露 electron 内置 API（用于 webview 的 getWebContentsId 等）
if (process.contextIsolated) {
  try {
    contextBridge.exposeInMainWorld('electron', electronAPI)
    contextBridge.exposeInMainWorld('collector', collectorAPI)
  } catch (error) {
    console.error(error)
  }
} else {
  // @ts-ignore（非生产环境）
  window.electron = electronAPI
  // @ts-ignore
  window.collector = collectorAPI
}
