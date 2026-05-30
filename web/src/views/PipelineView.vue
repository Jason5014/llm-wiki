<template>
  <div class="pipeline-view">
    <!-- 阶段状态 -->
    <el-card class="stage-card">
      <div class="stage-steps">
        <div
          v-for="stage in stages"
          :key="stage.key"
          class="stage-step"
          :class="getStageClass(stage)"
        >
          <div class="stage-icon">{{ stage.icon }}</div>
          <div class="stage-label">{{ stage.label }}</div>
          <div class="stage-count">{{ getStageCount(stage) }}</div>
        </div>
      </div>

      <div class="pipeline-actions">
        <el-button type="primary" @click="runPipeline('all')" :loading="running">
          ▶ 完整流水线
        </el-button>
        <el-button @click="runPipeline('source')" :disabled="running">仅 Source 摘要</el-button>
        <el-button @click="runPipeline('extract')" :disabled="running">仅实体/概念抽取</el-button>
        <el-button @click="runPipeline('index')" :disabled="running">仅重建索引</el-button>
        <el-checkbox v-model="forceRun" label="强制重新处理" />
      </div>
    </el-card>

    <!-- 实时日志 -->
    <el-card class="log-card" v-if="currentTask">
      <template #header>
        <div class="log-header">
          <span>处理日志 — {{ currentTask.task_id }}</span>
          <el-tag :type="getTaskTagType(currentTask.status)">{{ currentTask.status }}</el-tag>
          <el-progress
            v-if="currentTask.total"
            :percentage="Math.round(currentTask.progress || 0)"
            style="width: 200px; margin-left: 16px"
          />
        </div>
      </template>
      <div ref="logEl" class="log-content">
        <div v-for="(log, i) in logs" :key="i" class="log-line" :class="log.type">
          <span class="log-time">{{ log.time }}</span>
          <span class="log-msg">{{ log.msg }}</span>
        </div>
      </div>
    </el-card>

    <!-- 文档管理 -->
    <el-card class="doc-card">
      <template #header>
        <div class="doc-header">
          <span>文档管理（{{ totalDocs }} 篇）</span>
          <div>
            <el-upload
              :show-file-list="false"
              :before-upload="uploadFile"
              multiple
              accept=".md,.txt,.pdf,.html"
            >
              <el-button size="small"><el-icon><Upload /></el-icon> 导入文件</el-button>
            </el-upload>
          </div>
        </div>
      </template>

      <el-table :data="rawDocs" size="small" max-height="300">
        <el-table-column prop="doc_id" label="文档 ID" />
        <el-table-column label="操作" width="140" align="right">
          <template #default="{ row }">
            <el-button size="small" text @click="reprocessDoc(row.doc_id)">重处理</el-button>
            <el-button size="small" text type="danger" @click="deleteDoc(row.doc_id)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="totalDocs > pageSize"
        v-model:current-page="currentPage"
        :page-size="pageSize"
        :total="totalDocs"
        layout="prev, pager, next"
        @current-change="loadDocs"
        style="margin-top: 12px"
      />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { collectApi, processApi } from '../api'
import { useKbStore } from '../stores/kb'

const route = useRoute()
const kbStore = useKbStore()

const running = ref(false)
const forceRun = ref(false)
const currentTask = ref<any>(null)
const logs = ref<{ time: string; msg: string; type: string }[]>([])
const logEl = ref<HTMLElement | null>(null)

const rawDocs = ref<any[]>([])
const totalDocs = ref(0)
const currentPage = ref(1)
const pageSize = 20

const kbId = computed(() => route.params.kbId as string)
const kb = computed(() => kbStore.kbList.find(k => k.kb_id === kbId.value))

const stages = [
  { key: 'raw', icon: '📥', label: '数据采集', statKey: 'raw_count' },
  { key: 'source', icon: '📄', label: 'Source 摘要', statKey: 'source_count' },
  { key: 'extract', icon: '🔍', label: '实体/概念抽取', statKey: '_extract' },
  { key: 'index', icon: '⚡', label: '建立索引', statKey: '_index' },
]

function getStageCount(stage: any) {
  if (!kb.value?.stats) return '—'
  const s = kb.value.stats
  if (stage.statKey === '_extract') return `${s.entity_count ?? 0} / ${s.concept_count ?? 0}`
  if (stage.statKey === '_index') return s.indexed ? '✅' : '—'
  if (!stage.statKey) return '—'
  return s[stage.statKey as keyof typeof s] ?? '—'
}

function getStageClass(stage: any) {
  if (!kb.value?.stats) return ''
  const s = kb.value.stats
  if (stage.key === 'raw' && s.raw_count > 0) return 'done'
  if (stage.key === 'source' && s.source_count > 0) return 'done'
  if (stage.key === 'extract' && (s.entity_count > 0 || s.concept_count > 0)) return 'done'
  if (stage.key === 'index' && s.indexed) return 'done'
  return ''
}

function getTaskTagType(status: string) {
  return status === 'done' ? 'success' : status === 'error' ? 'danger' : status === 'running' ? 'warning' : 'info'
}

function addLog(msg: string, type = 'info') {
  const now = new Date().toLocaleTimeString()
  logs.value.push({ time: now, msg, type })
  nextTick(() => {
    if (logEl.value) logEl.value.scrollTop = logEl.value.scrollHeight
  })
}

async function runPipeline(stage: string) {
  if (!kbId.value) return
  running.value = true
  logs.value = []
  currentTask.value = null

  try {
    const resp = await processApi.run(kbId.value, { stage: stage as any, force: forceRun.value })
    currentTask.value = resp.data
    addLog(`流水线已启动，task_id: ${resp.data.task_id}`)

    // SSE 监听进度
    const source = processApi.streamTask(kbId.value, resp.data.task_id)
    source.onmessage = (event) => {
      if (!event.data) return
      try {
        const data = JSON.parse(event.data)
        // level=warning → 红色日志但不中断；status=error → 致命错误
        const logType = (data.status === 'error' || data.level === 'warning') ? 'error' : 'info'
        if (data.message) addLog(data.message, logType)
        if (data.progress !== undefined) {
          currentTask.value.progress = data.progress
          currentTask.value.completed = data.completed
          currentTask.value.total = data.total
        }
        if (data.status === 'done') {
          currentTask.value.status = 'done'
          addLog('✅ 流水线全部完成', 'success')
          source.close()
          running.value = false
          kbStore.loadKbList()
        } else if (data.status === 'error') {
          currentTask.value.status = 'error'
          addLog('❌ 处理出错', 'error')
          source.close()
          running.value = false
        }
      } catch (e) { /* ignore */ }
    }
    source.onerror = () => { source.close(); running.value = false }

  } catch (e: any) {
    ElMessage.error('启动失败：' + e.message)
    running.value = false
  }
}

async function loadDocs() {
  if (!kbId.value) return
  try {
    const resp = await collectApi.listRaw(kbId.value, currentPage.value, pageSize)
    rawDocs.value = resp.data.items
    totalDocs.value = resp.data.total
  } catch (e) { /* ignore */ }
}

async function uploadFile(file: File): Promise<boolean> {
  if (!kbId.value) { ElMessage.warning('请先选择知识库'); return false }
  try {
    const resp = await collectApi.uploadFile(kbId.value, file)
    ElMessage.success(`✅ ${resp.data.title} 导入成功`)
    loadDocs()
  } catch (e: any) {
    ElMessage.error('导入失败：' + e.message)
  }
  return false // 阻止默认上传行为
}

async function reprocessDoc(docId: string) {
  await processApi.run(kbId.value, { stage: 'source', doc_ids: [docId], force: true })
  ElMessage.success('已重新加入处理队列')
}

async function deleteDoc(docId: string) {
  await collectApi.deleteRaw(kbId.value, docId)
  ElMessage.success('已删除')
  loadDocs()
}

watch(kbId, () => { loadDocs(); kbStore.loadKbList() }, { immediate: true })
</script>

<style scoped>
.pipeline-view { height: 100%; overflow-y: auto; padding: 20px; display: flex; flex-direction: column; gap: 16px; }

.stage-steps { display: flex; gap: 0; margin-bottom: 16px; }
.stage-step {
  flex: 1;
  text-align: center;
  padding: 16px 8px;
  background: var(--el-fill-color-lighter);
  border: 1px solid var(--el-border-color);
  border-right: none;
}
.stage-step:first-child { border-radius: 6px 0 0 6px; }
.stage-step:last-child { border-right: 1px solid var(--el-border-color); border-radius: 0 6px 6px 0; }
.stage-step.done { background: var(--el-color-success-light-9); border-color: var(--el-color-success-light-5); }

.stage-icon { font-size: 24px; margin-bottom: 4px; }
.stage-label { font-size: 12px; font-weight: 500; }
.stage-count { font-size: 18px; font-weight: 700; color: var(--el-color-primary); margin-top: 4px; }

.pipeline-actions { display: flex; align-items: center; flex-wrap: wrap; gap: 8px; }

.log-card { flex-shrink: 0; }
.log-header { display: flex; align-items: center; gap: 8px; }
.log-content {
  height: 200px;
  overflow-y: auto;
  font-family: 'JetBrains Mono', monospace;
  font-size: 12px;
  background: #1e1e1e;
  color: #d4d4d4;
  border-radius: 6px;
  padding: 12px;
}
.log-line { display: flex; gap: 8px; margin-bottom: 2px; }
.log-time { color: #888; flex-shrink: 0; }
.log-line.error .log-msg { color: #f48771; }
.log-line.success .log-msg { color: #89d185; }

.doc-header { display: flex; align-items: center; justify-content: space-between; }
</style>
