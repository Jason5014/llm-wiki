/**
 * 采集器全局状态
 */
import { defineStore } from 'pinia'
import { ref, computed, toRaw, isRef } from 'vue'

/**
 * 深度解包 Vue 响应式对象，确保可通过 Electron IPC 结构化克隆。
 * toRaw() 只解包顶层 Proxy，嵌套的 ref/proxy 需要递归处理。
 */
function deepToRaw<T>(obj: T): any {
  if (obj === null || typeof obj !== 'object') return obj
  // ref → 解包 .value
  if (isRef(obj)) return deepToRaw((obj as any).value)
  // Proxy → 取原始对象
  const raw = toRaw(obj)
  if (Array.isArray(raw)) return raw.map(item => deepToRaw(item))
  const result: Record<string, unknown> = {}
  for (const key of Object.keys(raw)) {
    result[key] = deepToRaw(raw[key])
  }
  return result
}

export interface QueueItem {
  id: string
  /** 后端 crawl_tasks 表的真实 ID（用于 API 更新） */
  backendId?: string
  /** 用户提交的原始 URL */
  url: string
  /** 提取后的规范 URL（知乎弹框等场景可能与 url 不同） */
  extractedUrl?: string
  title?: string
  status: 'pending' | 'processing' | 'done' | 'error'
  content?: string
  metadata?: Record<string, unknown>
  error?: string
  addedAt: Date
  savedAt?: Date
  docId?: string
}

export interface KBInfo {
  kb_id: string
  name: string
  description: string
  stats: {
    raw_count: number
    source_count: number
    entity_count: number
    concept_count: number
    indexed: boolean
  }
}

// 是否运行在 Electron 环境中
const isElectron = !!(window as any).collector

export const useCollectorStore = defineStore('collector', () => {
  // 当前知识库
  const currentKbId = ref<string>('')
  const kbList = ref<KBInfo[]>([])

  // 采集队列
  const queue = ref<QueueItem[]>([])
  const pendingCount = computed(() => queue.value.filter(i => i.status === 'pending').length)
  const doneCount = computed(() => queue.value.filter(i => i.status === 'done').length)

  // ── 队列持久化（服务端 SQLite）──

  /** 从后端加载全量历史任务（合并本地已有数据） */
  async function loadQueue() {
    if (!isElectron || !currentKbId.value) return
    try {
      const resp = await collector.getCrawlTasks({ kbId: currentKbId.value, limit: 200 })
      const tasks = resp.tasks as any[]

      // 保留本地已有的 content/metadata（提取结果）
      const localMap = new Map(queue.value.map(i => [i.id, i]))

      const items: QueueItem[] = tasks.map(t => {
        const local = localMap.get(t.id)
        // 也尝试按 URL 匹配本地项（本地临时 ID 与后端 ID 不同的情况）
        const localByUrl = !local ? queue.value.find(q => q.url === t.url) : local
        return {
          id: t.id,
          backendId: t.id,
          url: t.url,
          extractedUrl: localByUrl?.extractedUrl,
          title: localByUrl?.title || t.url,
          status: _mapStatusFromBackend(t.status),
          content: localByUrl?.content,
          metadata: localByUrl?.metadata || (t.doc_id ? { quality: undefined } : undefined),
          error: t.error || undefined,
          addedAt: new Date(t.created_at),
          docId: t.doc_id || localByUrl?.docId || undefined,
        }
      })

      // 补充仅存在于本地的项（刚添加还未同步到后端的）
      const backendIds = new Set(tasks.map(t => t.id))
      const localOnly = queue.value.filter(i => !backendIds.has(i.id))
      queue.value = [...localOnly, ...items]
    } catch (e) {
      console.warn('[Store] loadQueue error:', e)
    }
  }

  /** 后端状态 → 前端状态 */
  function _mapStatusFromBackend(s: string): QueueItem['status'] {
    if (s === 'running') return 'processing'
    if (s === 'failed') return 'error'
    if (s === 'done') return 'done'
    return 'pending'
  }

  /** 前端状态 → 后端状态 */
  function _mapStatusToBackend(s: QueueItem['status']): string {
    if (s === 'processing') return 'running'
    if (s === 'error') return 'failed'
    return s
  }

  // 设置
  const apiBaseUrl = ref('http://localhost:8765')

  // 浏览器当前 URL
  const browserUrl = ref('https://www.google.com')

  const collector = (window as any).collector

  // ─────────────────────────────────────────
  // Actions
  // ─────────────────────────────────────────

  async function loadSettings() {
    if (!isElectron) return
    const settings = await collector.getSettings()
    apiBaseUrl.value = settings.apiBaseUrl
    currentKbId.value = settings.currentKbId
    await loadQueue()
  }

  async function saveSettings() {
    if (!isElectron) return
    await collector.setSettings({
      apiBaseUrl: apiBaseUrl.value,
      currentKbId: currentKbId.value,
    })
  }

  async function loadKbList() {
    if (!isElectron) return
    try {
      const list = await collector.listKbs()
      kbList.value = list as KBInfo[]
      if (!currentKbId.value && list.length > 0) {
        currentKbId.value = (list[0] as KBInfo).kb_id
      }
    } catch (e) {
      console.error('加载知识库列表失败', e)
    }
  }

  async function createKb(params: { name: string; domain?: string[]; description?: string }): Promise<KBInfo> {
    if (!isElectron) throw new Error('请在 Electron 应用中操作')
    const kb = await collector.createKb(deepToRaw(params)) as KBInfo
    await loadKbList()           // 刷新列表
    currentKbId.value = kb.kb_id // 自动切换到新建的 KB
    await saveSettings()
    return kb
  }

  function addToQueue(url: string): QueueItem {
    const item: QueueItem = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
      url,
      status: 'pending',
      addedAt: new Date(),
    }
    queue.value.unshift(item)
    // 后台提交到服务端持久化（不阻塞 UI）
    if (isElectron && currentKbId.value) {
      collector.addCrawlTasks(currentKbId.value, [url])
        .then(() => loadQueue())  // 刷新以获取后端分配的真实 ID
        .catch((e: any) => console.warn('[Store] addToQueue backend sync error:', e))
    }
    return item
  }

  function updateQueueItem(id: string, updates: Partial<QueueItem>): void {
    const idx = queue.value.findIndex(i => i.id === id)
    if (idx !== -1) {
      queue.value[idx] = { ...queue.value[idx], ...updates }
      // 状态变更同步到后端（使用 backendId，跳过无 backendId 的本地临时项）
      if (updates.status && isElectron) {
        const backendId = queue.value[idx].backendId
        if (backendId) {
          collector.updateCrawlTask({
            taskId: backendId,
            status: _mapStatusToBackend(updates.status),
            error: updates.error,
            docId: updates.docId,
          }).catch((e: any) => console.warn('[Store] updateQueueItem backend sync error:', e))
        }
      }
    }
  }

  async function retryQueueItem(id: string): Promise<void> {
    const idx = queue.value.findIndex(i => i.id === id)
    if (idx !== -1) {
      const backendId = queue.value[idx].backendId
      queue.value[idx] = {
        ...queue.value[idx],
        status: 'pending',
        error: undefined,
        content: undefined,
        metadata: undefined,
        docId: undefined,
        title: undefined,
        extractedUrl: undefined,
      }
      // 同步到后端：重置为 pending
      if (isElectron && backendId) {
        try {
          await collector.updateCrawlTask({ taskId: backendId, status: 'pending' })
        } catch (e) {
          console.warn('[Store] retryQueueItem backend sync error:', e)
        }
      }
    }
  }

  async function saveCurrentPage(extractResult: {
    title: string
    content: string
    url: string
    metadata: Record<string, unknown>
  }): Promise<{ docId: string; quality?: any }> {
    if (!isElectron) throw new Error('请在 Electron 应用中操作')
    if (!currentKbId.value) throw new Error('请先选择知识库')
    const result = await collector.submitDoc(currentKbId.value, deepToRaw(extractResult))
    return { docId: result.doc_id, quality: result.quality }
  }

  async function recordEpisode(episode: Record<string, unknown>): Promise<void> {
    if (!isElectron || !currentKbId.value) return
    try {
      await collector.recordEpisode(currentKbId.value, deepToRaw(episode))
    } catch (e) {
      console.warn('[Store] recordEpisode error:', e)
    }
  }

  async function batchSave(): Promise<{ saved: number; qualities: any[] }> {
    const pendingItems = queue.value.filter(i => i.status === 'done' && !i.docId)
    if (!isElectron || !pendingItems.length || !currentKbId.value) return { saved: 0, qualities: [] }

    const docs = pendingItems.map(item => ({
      title: item.title || item.url,
      url: item.extractedUrl || item.url,   // 优先使用提取后的规范 URL
      content: item.content || '',
      metadata: item.metadata || {},
    }))

    const result = await collector.batchSubmit(currentKbId.value, deepToRaw(docs))

    result.doc_ids.forEach((docId: string, i: number) => {
      updateQueueItem(pendingItems[i].id, { docId })
    })

    return { saved: result.saved, qualities: result.qualities || [] }
  }

  function clearQueue(): void {
    queue.value = queue.value.filter(i => i.status !== 'done')
  }

  // ─────────────────────────────────────────
  // 后端任务队列同步（自动化阶段）
  // ─────────────────────────────────────────

  /**
   * 从后端同步全量任务到本地队列。
   * 现在 loadQueue 已包含此功能，此函数保留兼容性。
   */
  async function syncBackendQueue(): Promise<number> {
    const before = queue.value.length
    await loadQueue()
    return queue.value.length - before
  }

  /**
   * 通知后端某个任务已完成
   */
  async function reportTaskDone(backendTaskId: string, docId?: string): Promise<void> {
    if (!isElectron) return
    try {
      await collector.updateCrawlTask({
        taskId: backendTaskId,
        status: 'done',
        docId,
      })
    } catch (e) {
      console.warn('[Store] reportTaskDone error:', e)
    }
  }

  /**
   * 通知后端某个任务失败
   */
  async function reportTaskFailed(backendTaskId: string, error: string): Promise<void> {
    if (!isElectron) return
    try {
      await collector.updateCrawlTask({
        taskId: backendTaskId,
        status: 'failed',
        error,
      })
    } catch (e) {
      console.warn('[Store] reportTaskFailed error:', e)
    }
  }

  return {
    currentKbId,
    kbList,
    queue,
    pendingCount,
    doneCount,
    apiBaseUrl,
    browserUrl,
    loadSettings,
    saveSettings,
    loadKbList,
    createKb,
    addToQueue,
    updateQueueItem,
    retryQueueItem,
    loadQueue,
    saveCurrentPage,
    batchSave,
    clearQueue,
    syncBackendQueue,
    reportTaskDone,
    reportTaskFailed,
    recordEpisode,
  }
})
