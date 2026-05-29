/**
 * 知识库 Pinia Store
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { kbApi } from '../api'

export interface KBStats {
  raw_count: number
  source_count: number
  entity_count: number
  concept_count: number
  indexed: boolean
}

export interface KBDetail {
  kb_id: string
  name: string
  description: string
  domain: string
  language: string
  status: string
  created_at: string
  updated_at: string
  stats: KBStats
}

export const useKbStore = defineStore('kb', () => {
  const kbList = ref<KBDetail[]>([])
  const currentKbId = ref('')
  const loading = ref(false)

  const currentKb = computed(() =>
    kbList.value.find(kb => kb.kb_id === currentKbId.value)
  )

  async function loadKbList() {
    loading.value = true
    try {
      const resp = await kbApi.list()
      kbList.value = resp.data
    } finally {
      loading.value = false
    }
  }

  async function createKb(data: {
    name: string; description?: string; domain?: string[]
  }) {
    const resp = await kbApi.create(data)
    kbList.value.push(resp.data)
    return resp.data
  }

  async function deleteKb(kbId: string) {
    await kbApi.delete(kbId)
    kbList.value = kbList.value.filter(kb => kb.kb_id !== kbId)
    if (currentKbId.value === kbId) {
      currentKbId.value = kbList.value[0]?.kb_id || ''
    }
  }

  function setCurrentKb(kbId: string) {
    currentKbId.value = kbId
  }

  return {
    kbList,
    currentKbId,
    currentKb,
    loading,
    loadKbList,
    createKb,
    deleteKb,
    setCurrentKb,
  }
})
