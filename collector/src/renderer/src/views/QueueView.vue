<template>
  <div class="queue-view">
    <!--
      后台采集用的隐藏 webview
      - 必须给 1px 尺寸，Electron webview 零尺寸时无法正常渲染页面
      - 用 position:fixed 移到屏幕外，opacity:0 防止闪烁
      - 与主浏览器共用同一 session，携带相同 Cookie（已登录状态）
    -->
    <webview
      ref="bgWebviewEl"
      src="about:blank"
      partition="persist:wiki-collector"
      webpreferences="contextIsolation=false"
      style="position:fixed;left:-2px;top:-2px;width:1px;height:1px;opacity:0;pointer-events:none;z-index:-9999;"
    />

    <!-- 工具栏 -->
    <div class="toolbar">
      <span class="title">采集队列</span>
      <el-space wrap>
        <!-- 自动保存开关 -->
        <el-switch
          v-model="autoSave"
          size="small"
          active-text="自动保存"
          inactive-text="手动确认"
          style="--el-switch-on-color: var(--el-color-success)"
        />

        <!-- 自动轮询后台队列 -->
        <el-switch
          v-model="autoPoll"
          size="small"
          active-text="自动采集"
          inactive-text="手动触发"
          style="--el-switch-on-color: var(--el-color-primary)"
        />

        <el-button size="small" @click="openBatchDialog" type="primary" :disabled="isProcessing">
          <el-icon><Plus /></el-icon> 批量添加 URL
        </el-button>

        <el-button
          size="small"
          @click="syncAndProcess"
          :loading="isSyncing"
          :disabled="isProcessing"
          title="从后端任务队列拉取待处理 URL"
        >
          <el-icon><Refresh /></el-icon> 同步后台任务
        </el-button>

        <!-- 开始 / 停止 切换 -->
        <el-button
          v-if="!isProcessing"
          size="small"
          type="success"
          @click="processQueue"
          :disabled="!store.pendingCount"
        >
          <el-icon><VideoPlay /></el-icon> 开始采集（{{ store.pendingCount }}）
        </el-button>
        <el-button
          v-else
          size="small"
          type="warning"
          @click="stopProcessing"
        >
          ⏹ 停止
        </el-button>

        <el-button
          size="small"
          @click="saveAllDone"
          :disabled="!unsavedDoneItems.length || isProcessing"
        >
          <el-icon><Upload /></el-icon> 批量保存（{{ unsavedDoneItems.length }}）
        </el-button>

        <el-button size="small" @click="store.clearQueue()" :disabled="isProcessing">
          <el-icon><Delete /></el-icon> 清除已完成
        </el-button>
      </el-space>
    </div>

    <!-- 进度条（采集进行中才显示） -->
    <div v-if="isProcessing" class="progress-bar">
      <el-progress
        :percentage="progressPct"
        :striped="true"
        :striped-flow="true"
        :duration="8"
        :show-text="false"
        style="flex:1"
      />
      <span class="progress-label">{{ progressLabel }}</span>
    </div>

    <!-- 统计栏 -->
    <div class="stats-bar">
      <el-tag>全部 {{ store.queue.length }}</el-tag>
      <el-tag type="warning">待处理 {{ store.pendingCount }}</el-tag>
      <el-tag type="success">已提取 {{ doneCount }}</el-tag>
      <el-tag type="info">已保存 {{ savedCount }}</el-tag>
      <el-tag type="danger">失败 {{ errorCount }}</el-tag>
    </div>

    <!-- 队列列表 -->
    <div class="queue-list" v-if="store.queue.length">
      <div
        v-for="item in store.queue"
        :key="item.id"
        class="queue-item"
        :class="item.status"
      >
        <div class="item-header">
          <el-icon class="status-icon">
            <Loading v-if="item.status === 'processing'" class="rotating" />
            <CircleCheck v-else-if="item.status === 'done'" style="color: var(--el-color-success)" />
            <CircleClose v-else-if="item.status === 'error'" style="color: var(--el-color-danger)" />
            <Clock v-else />
          </el-icon>
          <span class="item-title">{{ item.title || item.url }}</span>
          <el-tag v-if="item.docId" type="success" size="small">已保存</el-tag>
        </div>
        <div class="item-url">
          {{ item.extractedUrl || item.url }}
          <span v-if="item.extractedUrl && item.extractedUrl !== item.url" class="item-url-original">
            ← {{ item.url }}
          </span>
        </div>
        <div class="item-error" v-if="item.error">{{ item.error }}</div>
      </div>
    </div>

    <el-empty v-else description="队列为空，去浏览页面采集内容吧" />

    <!-- 批量添加 URL 弹窗 -->
    <el-dialog v-model="showBatchDialog" title="批量添加 URL" width="560px">
      <p style="margin-top:0;color:var(--el-text-color-secondary)">
        每行一个 URL，支持知乎文章/问题、小红书笔记及任意网页
      </p>
      <el-input
        v-model="batchUrlsText"
        type="textarea"
        :rows="10"
        placeholder="https://zhuanlan.zhihu.com/p/...&#10;https://www.zhihu.com/question/...&#10;https://www.xiaohongshu.com/explore/...&#10;https://sspai.com/post/..."
      />
      <template #footer>
        <el-button @click="showBatchDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmBatchAdd" :disabled="!batchUrlCount">
          添加 {{ batchUrlCount }} 个 URL
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useCollectorStore, type QueueItem } from '../stores/collector'
import { extract } from '../extractors'

const store = useCollectorStore()

// ── refs ─────────────────────────────────────────────────────

const bgWebviewEl = ref<any>(null)    // 隐藏 webview，用于后台加载页面
const isProcessing = ref(false)
const isSyncing = ref(false)
const autoSave = ref(false)           // 采集后是否自动提交到知识库
const autoPoll = ref(false)           // 自动轮询后端任务队列
const showBatchDialog = ref(false)
const batchUrlsText = ref('')

// 自动轮询定时器（30s 间隔）
let pollTimer: ReturnType<typeof setInterval> | null = null
const POLL_INTERVAL_MS = 30_000

// ── 统计 computed ─────────────────────────────────────────────

const doneCount = computed(() => store.queue.filter(i => i.status === 'done').length)
const savedCount = computed(() => store.queue.filter(i => !!i.docId).length)
const errorCount = computed(() => store.queue.filter(i => i.status === 'error').length)
const unsavedDoneItems = computed(() =>
  store.queue.filter(i => i.status === 'done' && !i.docId)
)
const batchUrlCount = computed(() =>
  batchUrlsText.value
    .split('\n')
    .map(l => l.trim())
    .filter(l => l.startsWith('http')).length
)

// ── 进度 ─────────────────────────────────────────────────────

const progressPct = computed(() => {
  const total = store.queue.length
  if (!total) return 0
  const done = store.queue.filter(i => i.status !== 'pending').length
  return Math.round((done / total) * 100)
})

const progressLabel = computed(() => {
  const item = store.queue.find(i => i.status === 'processing')
  if (!item) return '处理中...'
  const host = (() => { try { return new URL(item.url).hostname } catch { return item.url } })()
  return `正在采集：${host}`
})

// ── 后端队列同步 + 自动轮询 ─────────────────────────────────

/**
 * 从后端拉取 pending 任务 → 加入本地队列 → 自动开始采集（如已启用）
 */
async function syncAndProcess() {
  isSyncing.value = true
  try {
    const added = await store.syncBackendQueue()
    if (added > 0) {
      ElMessage.info(`已从后台同步 ${added} 个新任务`)
      // 若已启用自动采集且当前不在处理中，立即开始
      if (autoSave.value && !isProcessing.value && store.pendingCount > 0) {
        processQueue()
      }
    }
  } finally {
    isSyncing.value = false
  }
}

function startPoll() {
  if (pollTimer) return
  // 立即触发一次
  syncAndProcess()
  pollTimer = setInterval(syncAndProcess, POLL_INTERVAL_MS)
}

function stopPoll() {
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null }
}

// autoPoll 开关变化时启停定时器
watch(autoPoll, (val) => {
  if (val) startPoll()
  else stopPoll()
})

onUnmounted(() => stopPoll())

// ── 批量添加 ──────────────────────────────────────────────────

function openBatchDialog() {
  batchUrlsText.value = ''
  showBatchDialog.value = true
}

function confirmBatchAdd() {
  const urls = batchUrlsText.value
    .split('\n')
    .map(l => l.trim())
    .filter(l => l.startsWith('http'))
  for (const url of urls) {
    store.addToQueue(url)
  }
  showBatchDialog.value = false
  ElMessage.success(`已添加 ${urls.length} 个 URL`)
}

// ── 采集引擎 ──────────────────────────────────────────────────

/**
 * 批量处理队列：逐个导航到 URL → 等待加载 → 提取内容 → 可选自动保存
 */
async function processQueue() {
  if (!store.currentKbId) {
    ElMessage.warning('请先选择知识库')
    return
  }
  if (!bgWebviewEl.value) {
    ElMessage.error('后台浏览器组件未就绪，请稍后重试')
    return
  }

  isProcessing.value = true
  const pendingItems = store.queue.filter(i => i.status === 'pending')
  let successCount = 0
  let failCount = 0

  for (const item of pendingItems) {
    // 检查用户是否点击了"停止"
    if (!isProcessing.value) {
      // 将当前项恢复为 pending，下次继续
      store.updateQueueItem(item.id, { status: 'pending', error: undefined })
      break
    }

    store.updateQueueItem(item.id, { status: 'processing' })

    try {
      // ① 导航到目标 URL，等待页面加载 + SPA 渲染
      await loadUrlAndWait(bgWebviewEl.value, item.url)

      // ② 用 Provider/Registry 提取内容
      const result = await extract(bgWebviewEl.value, item.url)

      // ③ 更新队列项
      const updates: Partial<QueueItem> = {
        status: 'done',
        title: result.title,
        content: result.content,
        metadata: result.metadata,
      }
      // 若提取到的规范 URL 与原始 URL 不同（知乎弹框场景），记录下来
      if (result.url && result.url !== item.url) {
        updates.extractedUrl = result.url
      }
      store.updateQueueItem(item.id, updates)
      successCount++

      // ④ 自动保存（可选）
      let savedDocId: string | undefined
      if (autoSave.value) {
        try {
          savedDocId = await store.saveCurrentPage({
            title: result.title,
            url: result.url,
            content: result.content,
            metadata: result.metadata,
          })
          store.updateQueueItem(item.id, { docId: savedDocId })
        } catch (saveErr: any) {
          // 自动保存失败不影响采集状态，只打印警告
          console.warn('[Queue] auto-save failed for', item.url, saveErr.message)
        }
      }

      // ⑤ 回写后端任务队列状态（自动化驱动场景）
      const backendId = (item.metadata as any)?.backendTaskId as string | undefined
      if (backendId) await store.reportTaskDone(backendId, savedDocId)

    } catch (e: any) {
      store.updateQueueItem(item.id, { status: 'error', error: e.message })
      failCount++

      // 回写后端：标记失败
      const backendId = (item.metadata as any)?.backendTaskId as string | undefined
      if (backendId) await store.reportTaskFailed(backendId, e.message)
    }

    // 请求间隔：降低被反爬机制检测的风险
    if (isProcessing.value) {
      await sleep(2000)
    }
  }

  isProcessing.value = false
  if (successCount + failCount > 0) {
    ElMessage.success(`采集完成：✅ ${successCount} 成功，❌ ${failCount} 失败`)
  }
}

function stopProcessing() {
  isProcessing.value = false
  ElMessage.info('采集将在当前页面处理完成后停止')
}

/**
 * 导航隐藏 webview 到指定 URL，等待 did-stop-loading + 额外渲染时间
 *
 * 超时默认 30s。SPA 渲染额外等待 2s（知乎/小红书需要水合时间）。
 */
function loadUrlAndWait(webview: any, url: string, timeoutMs = 30_000): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      cleanup()
      reject(new Error('页面加载超时（30s）'))
    }, timeoutMs)

    const onStop = () => {
      cleanup()
      // 等待 SPA 完成首屏渲染（React/Vue app 在 network idle 后还需要水合时间）
      setTimeout(resolve, 2000)
    }

    const onFail = (event: any) => {
      // ERR_ABORTED (-3)：重定向过程中常见，不是真正失败，忽略
      if (event.errorCode === -3) return
      // 只处理主帧失败
      if (event.isMainFrame === false) return
      cleanup()
      reject(new Error(`加载失败 [${event.errorCode}]: ${event.errorDescription || '未知错误'}`))
    }

    function cleanup() {
      clearTimeout(timer)
      webview.removeEventListener('did-stop-loading', onStop)
      webview.removeEventListener('did-fail-load', onFail)
    }

    webview.addEventListener('did-stop-loading', onStop, { once: true })
    webview.addEventListener('did-fail-load', onFail)
    webview.loadURL(url)
  })
}

function sleep(ms: number): Promise<void> {
  return new Promise(r => setTimeout(r, ms))
}

// ── 批量保存 ──────────────────────────────────────────────────

async function saveAllDone() {
  if (!store.currentKbId) {
    ElMessage.warning('请先选择知识库')
    return
  }
  const count = unsavedDoneItems.value.length
  try {
    await store.batchSave()
    ElMessage.success(`已保存 ${count} 篇文档到「${store.kbList.find(k => k.kb_id === store.currentKbId)?.name ?? store.currentKbId}」`)
  } catch (e: any) {
    ElMessage.error(`保存失败：${e.message}`)
  }
}
</script>

<style scoped>
.queue-view {
  display: flex;
  flex-direction: column;
  flex: 1;
  overflow: hidden;
}

.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color);
  flex-shrink: 0;
  gap: 8px;
}
.toolbar .title {
  font-size: 15px;
  font-weight: 600;
  flex-shrink: 0;
}

.progress-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 16px;
  background: var(--el-color-warning-light-9);
  border-bottom: 1px solid var(--el-color-warning-light-5);
  flex-shrink: 0;
}
.progress-label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 320px;
}

.stats-bar {
  display: flex;
  gap: 8px;
  padding: 8px 16px;
  background: var(--el-fill-color-lighter);
  border-bottom: 1px solid var(--el-border-color);
  flex-shrink: 0;
}

.queue-list {
  flex: 1;
  overflow-y: auto;
}

.queue-item {
  padding: 10px 16px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  border-left: 3px solid var(--el-border-color);
}
.queue-item.done    { border-left-color: var(--el-color-success); }
.queue-item.error   { border-left-color: var(--el-color-danger); }
.queue-item.processing { border-left-color: var(--el-color-warning); }

.item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
.status-icon { flex-shrink: 0; }

.item-title {
  flex: 1;
  font-size: 13px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.item-url {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.item-url-original {
  color: var(--el-text-color-placeholder);
  font-size: 11px;
}

.item-error {
  font-size: 12px;
  color: var(--el-color-danger);
  margin-top: 2px;
}

.rotating {
  animation: rotate 1s linear infinite;
}
@keyframes rotate {
  from { transform: rotate(0deg); }
  to   { transform: rotate(360deg); }
}
</style>
