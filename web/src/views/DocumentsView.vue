<template>
  <div class="docs-view">
    <div class="docs-header">
      <h2>原始文档</h2>
      <el-tag type="info" size="large">共 {{ total }} 篇</el-tag>
    </div>

    <!-- 文档列表 -->
    <el-table
      :data="docs"
      v-loading="loading"
      stripe
      highlight-current-row
      style="width: 100%"
      @row-click="openDoc"
      row-class-name="doc-row"
    >
      <el-table-column prop="title" label="标题" min-width="220" show-overflow-tooltip>
        <template #default="{ row }">
          <div class="cell-title">{{ row.title }}</div>
          <div class="cell-url" v-if="row.url">{{ row.url }}</div>
        </template>
      </el-table-column>
      <el-table-column label="质检" width="160" align="center">
        <template #default="{ row }">
          <template v-if="row.quality">
            <el-tag
              :type="qualityType(row.quality.action)"
              size="small"
              effect="dark"
            >
              {{ qualityLabel(row.quality.action) }}
            </el-tag>
            <span class="quality-score">{{ row.quality.score }}</span>
            <div class="quality-issues" v-if="row.quality.issues?.length">
              <el-tag
                v-for="issue in row.quality.issues"
                :key="issue"
                size="small"
                type="warning"
                effect="plain"
                class="issue-tag"
              >
                {{ issue }}
              </el-tag>
            </div>
          </template>
          <span v-else class="no-quality">—</span>
        </template>
      </el-table-column>
      <el-table-column prop="crawled_at" label="采集时间" width="170" align="center">
        <template #default="{ row }">
          <span class="cell-date">{{ row.crawled_at || '—' }}</span>
        </template>
      </el-table-column>
      <el-table-column prop="char_count" label="字数" width="90" align="right">
        <template #default="{ row }">
          <span class="cell-count">{{ formatCount(row.char_count) }}</span>
        </template>
      </el-table-column>
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.has_source ? 'success' : 'warning'" size="small" effect="light">
            {{ row.has_source ? '已处理' : '待处理' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140" align="center" fixed="right">
        <template #default="{ row }">
          <el-button-group>
            <el-button size="small" type="primary" plain @click.stop="openDoc(row)">
              <el-icon><View /></el-icon> 查看
            </el-button>
            <el-button size="small" type="danger" plain @click.stop="deleteDoc(row)">
              <el-icon><Delete /></el-icon>
            </el-button>
          </el-button-group>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination-wrap">
      <el-pagination
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        :page-sizes="[20, 50, 100]"
        layout="total, sizes, prev, pager, next, jumper"
        background
        @current-change="loadDocs"
        @size-change="onPageSizeChange"
      />
    </div>

    <!-- 内容预览抽屉 -->
    <el-drawer
      v-model="showDrawer"
      :title="currentDoc?.title || '文档预览'"
      direction="rtl"
      size="55%"
      destroy-on-close
    >
      <div v-if="currentDoc" class="doc-preview">
        <el-descriptions :column="2" size="small" border class="doc-meta">
          <el-descriptions-item label="标题" :span="2">{{ currentDoc.title }}</el-descriptions-item>
          <el-descriptions-item label="采集时间">{{ currentDoc.crawled_at || '—' }}</el-descriptions-item>
          <el-descriptions-item label="字数">{{ currentDoc.char_count?.toLocaleString() }}</el-descriptions-item>
          <el-descriptions-item label="来源" :span="2" v-if="currentDoc.url">
            <a :href="currentDoc.url" target="_blank" class="doc-link">{{ currentDoc.url }}</a>
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="currentDoc.has_source ? 'success' : 'warning'" size="small">
              {{ currentDoc.has_source ? '已处理' : '待处理' }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="doc_id">
            <code style="font-size:12px">{{ currentDoc.doc_id }}</code>
          </el-descriptions-item>
        </el-descriptions>

        <!-- 质检详情 -->
        <div v-if="currentDoc.quality" class="quality-detail">
          <h4>质检报告</h4>
          <el-descriptions :column="2" size="small" border>
            <el-descriptions-item label="综合评分">
              <span class="score-big" :class="qualityColor(currentDoc.quality.score)">
                {{ currentDoc.quality.score }}
              </span>
              / 1.0
            </el-descriptions-item>
            <el-descriptions-item label="结果">
              <el-tag :type="qualityType(currentDoc.quality.action)" effect="dark">
                {{ qualityLabel(currentDoc.quality.action) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="文本完整性">
              <el-progress
                :percentage="Math.round((currentDoc.quality.completeness?.text || 0) * 100)"
                :stroke-width="10"
                :color="progressColor(currentDoc.quality.completeness?.text)"
                style="width: 160px"
              />
            </el-descriptions-item>
            <el-descriptions-item label="图片完整性">
              <el-progress
                :percentage="Math.round((currentDoc.quality.completeness?.images || 0) * 100)"
                :stroke-width="10"
                :color="progressColor(currentDoc.quality.completeness?.images)"
                style="width: 160px"
              />
            </el-descriptions-item>
            <el-descriptions-item label="问题" :span="2" v-if="currentDoc.quality.issues?.length">
              <el-tag
                v-for="issue in currentDoc.quality.issues"
                :key="issue"
                type="warning"
                effect="plain"
                style="margin-right: 4px"
              >
                {{ issueLabel(issue) }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item label="问题" :span="2" v-else>
              <span style="color: #67c23a">无</span>
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <el-divider />
        <div class="doc-content" v-loading="contentLoading">
          <div v-if="docContent" v-html="renderMarkdown(docContent)"></div>
          <el-empty v-else-if="!contentLoading" description="无法加载内容" />
        </div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { collectApi } from '../api'

const route = useRoute()
const kbId = route.params.kbId as string

const docs = ref<any[]>([])
const loading = ref(false)
const total = ref(0)
const currentPage = ref(1)
const pageSize = ref(20)

const showDrawer = ref(false)
const currentDoc = ref<any>(null)
const docContent = ref('')
const contentLoading = ref(false)

async function loadDocs() {
  loading.value = true
  try {
    const { data } = await collectApi.listRaw(kbId, currentPage.value, pageSize.value)
    docs.value = data.items
    total.value = data.total
  } catch {
    ElMessage.error('加载文档列表失败')
  } finally {
    loading.value = false
  }
}

function onPageSizeChange(size: number) {
  pageSize.value = size
  currentPage.value = 1
  loadDocs()
}

function formatCount(n: number): string {
  if (!n) return '—'
  if (n >= 10000) return (n / 10000).toFixed(1) + '万'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'k'
  return String(n)
}

function qualityType(action: string) {
  if (action === 'passed') return 'success'
  if (action === 'blocked') return 'danger'
  return 'warning'
}
function qualityLabel(action: string) {
  if (action === 'passed') return '通过'
  if (action === 'blocked') return '需登录'
  return '需重采'
}
function qualityColor(score: number) {
  if (score >= 0.8) return 'score-good'
  if (score >= 0.5) return 'score-warn'
  return 'score-bad'
}
function progressColor(val: number) {
  if (val >= 0.8) return '#67c23a'
  if (val >= 0.5) return '#e6a23c'
  return '#f56c6c'
}
function issueLabel(issue: string) {
  const map: Record<string, string> = {
    too_short: '内容过短',
    bad_title: '标题无效',
    truncated: '内容截断',
    blocked: '登录墙/验证码',
    images_missing: '图片缺失',
  }
  return map[issue] || issue
}

async function openDoc(row: any) {
  currentDoc.value = row
  showDrawer.value = true
  contentLoading.value = true
  docContent.value = ''
  try {
    const { data } = await collectApi.getRaw(kbId, row.doc_id)
    docContent.value = data.content
  } catch {
    ElMessage.error('加载文档内容失败')
  } finally {
    contentLoading.value = false
  }
}

async function deleteDoc(row: any) {
  await ElMessageBox.confirm(`确定删除「${row.title}」？`, '确认删除', {
    type: 'warning',
    confirmButtonText: '删除',
    cancelButtonText: '取消',
  })
  try {
    await collectApi.deleteRaw(kbId, row.doc_id)
    ElMessage.success('已删除')
    loadDocs()
  } catch {
    ElMessage.error('删除失败')
  }
}

/** Markdown → HTML */
function renderMarkdown(text: string): string {
  let html = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
    `<pre><code class="lang-${lang}">${code}</code></pre>`)
  html = html.replace(/^###### (.+)$/gm, '<h6>$1</h6>')
  html = html.replace(/^##### (.+)$/gm, '<h5>$1</h5>')
  html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>')
  html = html.replace(/^---+$/gm, '<hr/>')
  html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/_(.+?)_/g, '<em>$1</em>')
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g,
    '<img src="$2" alt="$1" style="max-width:100%;border-radius:4px;margin:4px 0" />')
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
  html = html.replace(/^\|(.+)\|$/gm, (_, row) => {
    const cells = row.split('|').map((c: string) => c.trim())
    if (cells.every((c: string) => /^[-:]+$/.test(c))) return ''
    return '<tr>' + cells.map((c: string) => `<td>${c}</td>`).join('') + '</tr>'
  })
  html = html.replace(/\n{2,}/g, '||PARA||')
  html = html.replace(/\n/g, '<br/>')
  html = html.replace(/\|\|PARA\|\|/g, '</p><p>')
  return '<p>' + html + '</p>'
}

onMounted(loadDocs)
</script>

<style scoped>
.docs-view { padding: 24px; height: 100%; overflow-y: auto; }
.docs-header { display: flex; align-items: center; gap: 12px; margin-bottom: 20px; }
.docs-header h2 { margin: 0; font-size: 20px; }

.doc-row { cursor: pointer; }
.doc-row:hover td { background: var(--el-color-primary-light-9) !important; }

.cell-title { font-weight: 500; font-size: 14px; line-height: 1.4; }
.cell-url { font-size: 12px; color: var(--el-text-color-placeholder); margin-top: 2px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cell-date { font-size: 13px; color: var(--el-text-color-secondary); }
.cell-count { font-size: 13px; font-family: monospace; color: var(--el-text-color-secondary); }

/* 质检列 */
.quality-score { font-size: 13px; font-weight: 600; margin-left: 4px; font-family: monospace; }
.quality-issues { margin-top: 4px; }
.issue-tag { margin: 1px 2px; font-size: 11px; }
.no-quality { color: var(--el-text-color-placeholder); }

/* 质检详情 */
.quality-detail { margin: 16px 0; }
.quality-detail h4 { margin: 0 0 10px; font-size: 15px; color: var(--el-text-color-primary); }
.score-big { font-size: 22px; font-weight: 700; font-family: monospace; }
.score-good { color: #67c23a; }
.score-warn { color: #e6a23c; }
.score-bad { color: #f56c6c; }

/* 分页 */
.pagination-wrap { display: flex; justify-content: center; margin-top: 20px; padding: 8px 0; }

/* 抽屉 */
.doc-preview { height: 100%; display: flex; flex-direction: column; }
.doc-meta { flex-shrink: 0; }
.doc-link { color: var(--el-color-primary); word-break: break-all; }
.doc-content { flex: 1; overflow-y: auto; font-size: 14px; line-height: 1.8; color: var(--el-text-color-primary); word-break: break-word; }
.doc-content :deep(h1), .doc-content :deep(h2), .doc-content :deep(h3) { margin: 20px 0 8px; font-weight: 600; border-bottom: 1px solid var(--el-border-color-lighter); padding-bottom: 6px; }
.doc-content :deep(h4), .doc-content :deep(h5), .doc-content :deep(h6) { margin: 16px 0 6px; font-weight: 600; }
.doc-content :deep(code) { background: var(--el-fill-color-light); padding: 2px 6px; border-radius: 3px; font-size: 13px; }
.doc-content :deep(pre) { background: #1e1e1e; color: #d4d4d4; padding: 14px; border-radius: 6px; overflow-x: auto; margin: 8px 0; }
.doc-content :deep(pre code) { background: none; padding: 0; color: inherit; }
.doc-content :deep(blockquote) { border-left: 3px solid var(--el-color-primary); padding-left: 12px; margin: 8px 0; color: var(--el-text-color-secondary); }
.doc-content :deep(img) { max-width: 100%; border-radius: 4px; margin: 6px 0; }
.doc-content :deep(li) { margin-left: 20px; list-style: disc; }
.doc-content :deep(hr) { border: none; border-top: 1px solid var(--el-border-color); margin: 16px 0; }
.doc-content :deep(a) { color: var(--el-color-primary); text-decoration: none; }
.doc-content :deep(a:hover) { text-decoration: underline; }
.doc-content :deep(tr) { border-bottom: 1px solid var(--el-border-color-lighter); }
.doc-content :deep(td) { padding: 6px 10px; font-size: 13px; }
</style>
