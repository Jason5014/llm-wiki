<template>
  <div class="wiki-view">
    <!-- 主内容区 -->
    <div class="wiki-main">
      <!-- 面包屑 -->
      <div class="breadcrumb" v-if="pageType && pageName">
        <el-breadcrumb separator="/">
          <el-breadcrumb-item @click="router.push({ name: 'Wiki', params: { kbId } })">
            {{ kbName }}
          </el-breadcrumb-item>
          <el-breadcrumb-item>{{ pageType }}</el-breadcrumb-item>
          <el-breadcrumb-item>{{ pageName }}</el-breadcrumb-item>
        </el-breadcrumb>
      </div>

      <!-- 加载状态 -->
      <el-skeleton :loading="loading" animated :rows="10" v-if="loading" style="padding: 20px" />

      <!-- Wiki 页面内容 -->
      <div v-else-if="content" class="wiki-content-wrapper">
        <div class="wiki-content" v-html="renderedContent" @click="handleLinkClick" />
      </div>

      <!-- index.md 入口 -->
      <div v-else-if="!pageType" class="wiki-index">
        <div class="wiki-content" v-html="renderedIndex" @click="handleLinkClick" />
      </div>

      <el-empty v-else description="页面不存在" />
    </div>

    <!-- 右侧关系图（实体/概念页面显示） -->
    <div class="wiki-mini-graph" v-if="pageType && pageName && (pageType === 'entity' || pageType === 'concept')">
      <div class="mini-graph-title">关联关系</div>
      <div ref="miniGraphEl" class="mini-graph-canvas" />
      <router-link
        :to="{ name: 'Graph', params: { kbId } }"
        class="view-full-graph"
      >
        在图谱中查看 →
      </router-link>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import MarkdownIt from 'markdown-it'
import { wikiApi } from '../api'
import { useKbStore } from '../stores/kb'

const router = useRouter()
const route = useRoute()
const kbStore = useKbStore()

const content = ref('')
const indexContent = ref('')
const loading = ref(false)
const miniGraphEl = ref<HTMLElement | null>(null)

const kbId = computed(() => route.params.kbId as string)
const pageType = computed(() => route.params.pageType as string)
const pageName = computed(() => route.params.name as string)
const kbName = computed(() => kbStore.kbList.find(k => k.kb_id === kbId.value)?.name || kbId.value)

// Markdown 渲染器（带 WikiLink 支持）
const md = new MarkdownIt({ html: false, linkify: true, typographer: true })

function renderWithWikiLinks(raw: string): string {
  // 替换 [[WikiLink|显示文本]] 和 [[WikiLink]]
  const processed = raw
    .replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, (_, target, display) => {
      const path = _resolveWikiPath(target)
      return `<a class="wiki-link" data-wiki="${target}" href="${path}">${display}</a>`
    })
    .replace(/\[\[([^\]]+)\]\]/g, (_, target) => {
      const display = target.split('/').pop() || target
      const path = _resolveWikiPath(target)
      return `<a class="wiki-link" data-wiki="${target}" href="${path}">${display}</a>`
    })
  return md.render(processed)
}

function _resolveWikiPath(target: string): string {
  if (target.includes('/')) {
    const parts = target.split('/')
    return `/kb/${kbId.value}/wiki/${parts[0]}/${parts.slice(1).join('/')}`
  }
  return '#'
}

const renderedContent = computed(() => content.value ? renderWithWikiLinks(content.value) : '')
const renderedIndex = computed(() => indexContent.value ? renderWithWikiLinks(indexContent.value) : '')

function handleLinkClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  const link = target.closest('a.wiki-link') as HTMLAnchorElement
  if (!link) return

  e.preventDefault()
  const wikiTarget = link.dataset.wiki
  if (!wikiTarget) return

  if (wikiTarget.includes('/')) {
    const parts = wikiTarget.split('/')
    router.push({ name: 'WikiPage', params: { kbId: kbId.value, pageType: parts[0], name: parts.slice(1).join('/') } })
  }
}

async function loadPage() {
  if (!kbId.value) return
  loading.value = true
  try {
    if (pageType.value && pageName.value) {
      const resp = await wikiApi.getPage(kbId.value, pageType.value, pageName.value)
      content.value = resp.data
    } else {
      const resp = await wikiApi.getIndex(kbId.value)
      indexContent.value = resp.data
    }
  } catch (e) {
    content.value = ''
    indexContent.value = ''
  } finally {
    loading.value = false
  }
}

watch([kbId, pageType, pageName], loadPage, { immediate: true })
</script>

<style scoped>
.wiki-view {
  display: flex;
  height: 100%;
  overflow: hidden;
}

.wiki-main {
  flex: 1;
  overflow-y: auto;
  padding: 20px 28px;
}

.breadcrumb {
  margin-bottom: 16px;
}
.breadcrumb :deep(.el-breadcrumb__item) {
  cursor: pointer;
}

.wiki-content-wrapper {
  max-width: 860px;
}

.wiki-mini-graph {
  width: 220px;
  flex-shrink: 0;
  border-left: 1px solid var(--el-border-color);
  padding: 16px;
  display: flex;
  flex-direction: column;
}
.mini-graph-title {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  text-transform: uppercase;
  margin-bottom: 8px;
}
.mini-graph-canvas {
  flex: 1;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}
.view-full-graph {
  display: block;
  text-align: center;
  font-size: 12px;
  color: var(--el-color-primary);
  margin-top: 8px;
  text-decoration: none;
}
.view-full-graph:hover { text-decoration: underline; }
</style>

<style>
/* WikiLink 全局样式（不用 scoped，因为是动态 HTML） */
a.wiki-link {
  color: var(--el-color-primary);
  background: rgba(64, 158, 255, 0.08);
  border-radius: 3px;
  padding: 0 3px;
  text-decoration: none;
  cursor: pointer;
}
a.wiki-link:hover {
  background: rgba(64, 158, 255, 0.18);
  text-decoration: underline;
}
</style>
