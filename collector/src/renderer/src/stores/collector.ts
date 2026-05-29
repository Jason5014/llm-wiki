/**
 * 采集器全局状态
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface QueueItem {
  id: string
  url: string
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

export const useCollectorStore = defineStore('collector', () => {
  // 当前知识库
  const currentKbId = ref<string>('')
  const kbList = ref<KBInfo[]>([])

  // 采集队列
  const queue = ref<QueueItem[]>([])
  const pendingCount = computed(() => queue.value.filter(i => i.status === 'pending').length)
  const doneCount = computed(() => queue.value.filter(i => i.status === 'done').length)

  // 设置
  const apiBaseUrl = ref('http://localhost:8000')

  // 浏览器当前 URL
  const browserUrl = ref('https://www.google.com')

  // ─────────────────────────────────────────
  // Actions
  // ─────────────────────────────────────────

  async function loadSettings() {
    const settings = await window.collector.getSettings()
    apiBaseUrl.value = settings.apiBaseUrl
    currentKbId.value = settings.currentKbId
  }

  async function saveSettings() {
    await window.collector.setSettings({
      apiBaseUrl: apiBaseUrl.value,
      currentKbId: currentKbId.value,
    })
  }

  async function loadKbList() {
    try {
      const list = await window.collector.listKbs()
      kbList.value = list as KBInfo[]
      if (!currentKbId.value && list.length > 0) {
        currentKbId.value = (list[0] as KBInfo).kb_id
      }
    } catch (e) {
      console.error('加载知识库列表失败', e)
    }
  }

  async function createKb(params: { name: string; domain?: string[]; description?: string }): Promise<KBInfo> {
    const kb = await window.collector.createKb(params) as KBInfo
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
    return item
  }

  function updateQueueItem(id: string, updates: Partial<QueueItem>): void {
    const idx = queue.value.findIndex(i => i.id === id)
    if (idx !== -1) {
      queue.value[idx] = { ...queue.value[idx], ...updates }
    }
  }

  async function saveCurrentPage(extractResult: {
    title: string
    content: string
    url: string
    metadata: Record<string, unknown>
  }): Promise<string> {
    if (!currentKbId.value) throw new Error('请先选择知识库')
    const result = await window.collector.submitDoc(currentKbId.value, extractResult)
    return result.doc_id
  }

  async function batchSave(): Promise<void> {
    const pendingItems = queue.value.filter(i => i.status === 'done' && !i.docId)
    if (!pendingItems.length || !currentKbId.value) return

    const docs = pendingItems.map(item => ({
      title: item.title || item.url,
      url: item.url,
      content: item.content || '',
      metadata: item.metadata || {},
    }))

    const result = await window.collector.batchSubmit(currentKbId.value, docs)

    result.doc_ids.forEach((docId: string, i: number) => {
      updateQueueItem(pendingItems[i].id, { docId })
    })
  }

  function clearQueue(): void {
    queue.value = queue.value.filter(i => i.status !== 'done')
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
    saveCurrentPage,
    batchSave,
    clearQueue,
  }
})
