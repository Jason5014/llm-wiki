<template>
  <div class="search-view">
    <div class="search-container">
      <h2 class="search-title">搜索知识库</h2>

      <!-- 搜索框 -->
      <el-input
        v-model="query"
        size="large"
        placeholder="输入问题或关键词，按 Enter 搜索..."
        @keyup.enter="doSearch"
        :loading="searching"
        class="search-input"
      >
        <template #prefix><el-icon><Search /></el-icon></template>
        <template #append>
          <el-button type="primary" @click="doSearch" :loading="searching">搜索</el-button>
        </template>
      </el-input>

      <!-- 结果区域 -->
      <div v-if="result" class="search-result">
        <!-- AI 回答 -->
        <div v-if="result.answer" class="answer-section">
          <div class="section-label">AI 回答</div>
          <div class="answer-content wiki-content" v-html="renderedAnswer" @click="handleLinkClick" />
          <div class="search-meta">搜索耗时：{{ result.search_time_ms?.toFixed(0) }}ms</div>
        </div>

        <!-- 引用来源 -->
        <div v-if="result.sources?.length" class="sources-section">
          <div class="section-label">引用来源</div>
          <div class="source-cards">
            <div
              v-for="src in result.sources"
              :key="src.path"
              class="source-card"
              @click="goToPage(src)"
            >
              <div class="source-header">
                <el-tag :type="getTagType(src.page_type)" size="small">{{ src.page_type }}</el-tag>
                <span class="source-name">{{ src.name }}</span>
                <span class="source-score">{{ (src.score * 100).toFixed(0) }}%</span>
              </div>
              <div class="source-snippet">{{ src.snippet }}</div>
            </div>
          </div>
        </div>

        <!-- 相关标签 -->
        <div v-if="result.related_entities?.length || result.related_concepts?.length" class="tags-section">
          <span
            v-for="name in result.related_entities"
            :key="'e:' + name"
            class="tag entity-tag"
            @click="goToWiki('entity', name)"
          >
            {{ name }}
          </span>
          <span
            v-for="name in result.related_concepts"
            :key="'c:' + name"
            class="tag concept-tag"
            @click="goToWiki('concept', name)"
          >
            {{ name }}
          </span>
        </div>
      </div>

      <!-- 历史记录 -->
      <div v-if="!result && history.length" class="history-section">
        <div class="section-label">搜索历史</div>
        <div class="history-list">
          <span
            v-for="q in history"
            :key="q"
            class="history-item"
            @click="query = q; doSearch()"
          >
            {{ q }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import MarkdownIt from 'markdown-it'
import { searchApi } from '../api'

const router = useRouter()
const route = useRoute()

const query = ref('')
const searching = ref(false)
const result = ref<any>(null)
const history = ref<string[]>([])

const kbId = computed(() => route.params.kbId as string)

const md = new MarkdownIt()

const renderedAnswer = computed(() => {
  if (!result.value?.answer) return ''
  const text = result.value.answer
    .replace(/\[\[([^\]|]+)\|([^\]]+)\]\]/g, (_: any, target: string, display: string) =>
      `<a class="wiki-link" data-wiki="${target}" href="#">${display}</a>`)
    .replace(/\[\[([^\]]+)\]\]/g, (_: any, target: string) =>
      `<a class="wiki-link" data-wiki="${target}" href="#">${target.split('/').pop()}</a>`)
  return md.render(text)
})

function handleLinkClick(e: MouseEvent) {
  const target = e.target as HTMLElement
  const link = target.closest('a.wiki-link') as HTMLAnchorElement
  if (!link) return
  e.preventDefault()
  const wikiTarget = link.dataset.wiki
  if (!wikiTarget) return
  if (wikiTarget.includes('/')) {
    const parts = wikiTarget.split('/')
    router.push({ name: 'WikiPage', params: { kbId: kbId.value, pageType: parts[0], name: parts[1] } })
  }
}

function getTagType(pageType: string) {
  return pageType === 'entity' ? 'primary' : pageType === 'concept' ? 'success' : 'info'
}

function goToPage(src: any) {
  router.push({ name: 'WikiPage', params: { kbId: kbId.value, pageType: src.page_type, name: src.name } })
}

function goToWiki(pageType: string, name: string) {
  router.push({ name: 'WikiPage', params: { kbId: kbId.value, pageType, name } })
}

async function doSearch() {
  if (!query.value.trim() || !kbId.value) return
  searching.value = true
  try {
    const resp = await searchApi.query(kbId.value, query.value)
    result.value = resp.data
    // 记录历史
    if (!history.value.includes(query.value)) {
      history.value.unshift(query.value)
      if (history.value.length > 10) history.value.pop()
    }
  } catch (e) {
    console.error(e)
  } finally {
    searching.value = false
  }
}

// 支持 URL 参数 ?q=xxx
onMounted(() => {
  const q = route.query.q as string
  if (q) { query.value = q; doSearch() }
})
</script>

<style scoped>
.search-view { height: 100%; overflow-y: auto; }
.search-container { max-width: 800px; margin: 0 auto; padding: 32px 20px; }
.search-title { margin-top: 0; margin-bottom: 24px; font-size: 22px; }
.search-input { margin-bottom: 24px; }

.section-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--el-text-color-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
}

.answer-section {
  background: var(--el-fill-color-lighter);
  border-radius: 10px;
  padding: 20px;
  margin-bottom: 20px;
  border: 1px solid var(--el-border-color);
}
.answer-content { line-height: 1.8; }
.search-meta { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 12px; }

.sources-section { margin-bottom: 20px; }
.source-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.source-card {
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  padding: 12px;
  cursor: pointer;
  transition: all 0.2s;
}
.source-card:hover { border-color: var(--el-color-primary); box-shadow: 0 2px 8px rgba(0,0,0,0.08); }
.source-header { display: flex; align-items: center; gap: 6px; margin-bottom: 6px; }
.source-name { font-size: 13px; font-weight: 500; flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.source-score { font-size: 12px; color: var(--el-color-success); }
.source-snippet { font-size: 12px; color: var(--el-text-color-secondary); line-height: 1.5; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }

.tags-section { display: flex; flex-wrap: wrap; gap: 8px; }
.tag { padding: 4px 10px; border-radius: 12px; font-size: 12px; cursor: pointer; }
.entity-tag { background: rgba(64, 158, 255, 0.1); color: var(--el-color-primary); }
.entity-tag:hover { background: rgba(64, 158, 255, 0.2); }
.concept-tag { background: rgba(103, 194, 58, 0.1); color: var(--el-color-success); }
.concept-tag:hover { background: rgba(103, 194, 58, 0.2); }

.history-section { margin-top: 24px; }
.history-list { display: flex; flex-wrap: wrap; gap: 8px; }
.history-item { padding: 4px 12px; border: 1px solid var(--el-border-color); border-radius: 12px; font-size: 13px; cursor: pointer; }
.history-item:hover { border-color: var(--el-color-primary); color: var(--el-color-primary); }
</style>
