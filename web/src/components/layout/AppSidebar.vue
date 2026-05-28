<template>
  <div class="sidebar">
    <div class="sidebar-header">
      <el-input v-model="search" placeholder="搜索文件..." size="small" clearable>
        <template #prefix><el-icon><Search /></el-icon></template>
      </el-input>
    </div>

    <div class="sidebar-content">
      <!-- 实体目录 -->
      <div class="tree-section">
        <div class="section-header" @click="collapsed.entity = !collapsed.entity">
          <el-icon><ArrowRight :class="{ rotated: !collapsed.entity }" /></el-icon>
          <span>📁 entity</span>
          <span class="count">{{ filteredEntities.length }}</span>
        </div>
        <template v-if="!collapsed.entity">
          <div
            v-for="page in filteredEntities"
            :key="page.name"
            class="tree-item"
            :class="{ active: isActive('entity', page.name) }"
            @click="goToPage('entity', page.name)"
          >
            {{ page.name }}
          </div>
        </template>
      </div>

      <!-- 概念目录 -->
      <div class="tree-section">
        <div class="section-header" @click="collapsed.concept = !collapsed.concept">
          <el-icon><ArrowRight :class="{ rotated: !collapsed.concept }" /></el-icon>
          <span>📁 concept</span>
          <span class="count">{{ filteredConcepts.length }}</span>
        </div>
        <template v-if="!collapsed.concept">
          <div
            v-for="page in filteredConcepts"
            :key="page.name"
            class="tree-item"
            :class="{ active: isActive('concept', page.name) }"
            @click="goToPage('concept', page.name)"
          >
            {{ page.name }}
          </div>
        </template>
      </div>

      <!-- 来源目录 -->
      <div class="tree-section">
        <div class="section-header" @click="collapsed.source = !collapsed.source">
          <el-icon><ArrowRight :class="{ rotated: !collapsed.source }" /></el-icon>
          <span>📁 source</span>
          <span class="count">{{ filteredSources.length }}</span>
        </div>
        <template v-if="!collapsed.source">
          <div
            v-for="page in filteredSources"
            :key="page.name"
            class="tree-item source"
            :class="{ active: isActive('source', page.name) }"
            @click="goToPage('source', page.name)"
          >
            {{ page.name }}
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { wikiApi } from '../../api'

const router = useRouter()
const route = useRoute()
const search = ref('')

const entities = ref<{ name: string; description: string }[]>([])
const concepts = ref<{ name: string; description: string }[]>([])
const sources = ref<{ name: string; description: string }[]>([])

const collapsed = ref({ entity: false, concept: false, source: true })

const kbId = computed(() => route.params.kbId as string)

const filteredEntities = computed(() =>
  entities.value.filter(p => !search.value || p.name.toLowerCase().includes(search.value.toLowerCase()))
)
const filteredConcepts = computed(() =>
  concepts.value.filter(p => !search.value || p.name.toLowerCase().includes(search.value.toLowerCase()))
)
const filteredSources = computed(() =>
  sources.value.filter(p => !search.value || p.name.toLowerCase().includes(search.value.toLowerCase()))
)

function isActive(pageType: string, name: string): boolean {
  return route.params.pageType === pageType && route.params.name === name
}

function goToPage(pageType: string, name: string) {
  router.push({ name: 'WikiPage', params: { kbId: kbId.value, pageType, name } })
}

async function loadPages() {
  if (!kbId.value) return
  try {
    const [e, c, s] = await Promise.all([
      wikiApi.listPages(kbId.value, 'entity', 1, 200),
      wikiApi.listPages(kbId.value, 'concept', 1, 200),
      wikiApi.listPages(kbId.value, 'source', 1, 200),
    ])
    entities.value = e.data.items
    concepts.value = c.data.items
    sources.value = s.data.items
  } catch (e) {
    console.error(e)
  }
}

watch(kbId, loadPages, { immediate: true })
</script>

<style scoped>
.sidebar {
  height: 100%;
  display: flex;
  flex-direction: column;
  font-size: 13px;
}
.sidebar-header {
  padding: 10px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.sidebar-content {
  flex: 1;
  overflow-y: auto;
}
.tree-section {
  border-bottom: 1px solid var(--el-border-color-lighter);
}
.section-header {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 8px 12px;
  cursor: pointer;
  font-weight: 500;
  color: var(--el-text-color-regular);
  user-select: none;
}
.section-header:hover {
  background: var(--el-fill-color-light);
}
.count {
  margin-left: auto;
  background: var(--el-fill-color);
  border-radius: 8px;
  padding: 0 6px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.tree-item {
  padding: 5px 12px 5px 28px;
  cursor: pointer;
  color: var(--el-text-color-regular);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.tree-item:hover { background: var(--el-fill-color-light); }
.tree-item.active { color: var(--el-color-primary); background: var(--el-color-primary-light-9); }
.tree-item.source { color: var(--el-text-color-secondary); font-size: 12px; }

.rotated { transform: rotate(90deg); }
</style>
