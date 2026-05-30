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

        <el-button
          v-if="errorCount > 0"
          size="small"
          type="warning"
          @click="retryAllErrors"
          :disabled="isProcessing"
        >
          <el-icon><Refresh /></el-icon> 重试全部失败（{{ errorCount }}）
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
        <div class="item-header" @click="item.status === 'done' && openPreview(item)">
          <el-icon class="status-icon">
            <Loading v-if="item.status === 'processing'" class="rotating" />
            <CircleCheck v-else-if="item.status === 'done'" style="color: var(--el-color-success)" />
            <CircleClose v-else-if="item.status === 'error'" style="color: var(--el-color-danger)" />
            <Clock v-else />
          </el-icon>
          <span class="item-title" :class="{ clickable: item.status === 'done' }">{{ item.title || item.url }}</span>
          <el-tag v-if="item.docId" type="success" size="small">已保存</el-tag>
        </div>
        <div class="item-url">
          {{ item.extractedUrl || item.url }}
          <span v-if="item.extractedUrl && item.extractedUrl !== item.url" class="item-url-original">
            ← {{ item.url }}
          </span>
        </div>
        <div class="item-error" v-if="item.error">
          {{ item.error }}
          <el-button size="small" type="warning" text @click="retryItem(item.id)">
            <el-icon><Refresh /></el-icon> 重新采集
          </el-button>
        </div>
      </div>
    </div>

    <el-empty v-else description="队列为空，去浏览页面采集内容吧" />

    <!-- 批量添加 URL 弹窗 -->
    <el-dialog v-model="showBatchDialog" title="批量添加 URL" width="600px">
      <!-- 预设 URL 分组 -->
      <div class="preset-section">
        <div class="preset-label">快速添加预设：</div>
        <div class="preset-groups">
          <el-button
            v-for="group in presetGroups"
            :key="group.name"
            size="small"
            plain
            @click="loadPreset(group)"
          >
            {{ group.name }}（{{ group.urls.length }}）
          </el-button>
          <el-button size="small" type="info" plain @click="openPresetEditor">
            <el-icon><Setting /></el-icon> 管理预设
          </el-button>
        </div>
      </div>

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

    <!-- 预设管理弹窗 -->
    <el-dialog v-model="showPresetEditor" title="管理预设 URL 分组" width="620px">
      <div class="preset-editor">
        <div v-for="(group, idx) in editablePresets" :key="idx" class="preset-edit-item">
          <div class="preset-edit-header">
            <el-input v-model="group.name" size="small" placeholder="分组名称" style="width: 160px" />
            <el-button size="small" type="danger" text @click="editablePresets.splice(idx, 1)">删除</el-button>
          </div>
          <el-input
            v-model="group.urlsText"
            type="textarea"
            :rows="3"
            placeholder="每行一个 URL"
            size="small"
          />
        </div>
        <el-button size="small" @click="editablePresets.push({ name: '', urls: [], urlsText: '' })" style="margin-top: 8px">
          + 添加分组
        </el-button>
      </div>
      <template #footer>
        <el-button @click="showPresetEditor = false">取消</el-button>
        <el-button type="primary" @click="savePresets">保存</el-button>
      </template>
    </el-dialog>

    <!-- 内容预览抽屉 -->
    <el-drawer
      v-model="showPreview"
      :title="previewItem?.title || '内容预览'"
      direction="rtl"
      size="50%"
    >
      <div v-if="previewItem" class="preview-content">
        <div class="preview-meta">
          <el-descriptions :column="1" size="small" border>
            <el-descriptions-item label="URL">{{ previewItem.extractedUrl || previewItem.url }}</el-descriptions-item>
            <el-descriptions-item label="状态">
              <el-tag type="success" size="small">已保存</el-tag>
              <el-tag v-if="previewItem.docId" size="small" style="margin-left:4px">doc_id: {{ previewItem.docId }}</el-tag>
            </el-descriptions-item>
            <el-descriptions-item v-if="previewItem.metadata?.quality" label="质检">
              <el-tag :type="previewItem.metadata.quality.action === 'passed' ? 'success' : 'warning'" size="small">
                {{ previewItem.metadata.quality.action }} ({{ previewItem.metadata.quality.score }})
              </el-tag>
              <span v-if="previewItem.metadata.quality.issues?.length" style="margin-left:4px;color:#e6a23c">
                {{ previewItem.metadata.quality.issues.join(', ') }}
              </span>
            </el-descriptions-item>
            <el-descriptions-item v-if="previewItem.metadata?.author" label="作者">{{ previewItem.metadata.author }}</el-descriptions-item>
            <el-descriptions-item v-if="previewItem.metadata?.date" label="日期">{{ previewItem.metadata.date }}</el-descriptions-item>
            <el-descriptions-item v-if="previewItem.metadata?.img_count" label="图片数">{{ previewItem.metadata.img_count }}</el-descriptions-item>
          </el-descriptions>
        </div>
        <el-divider />
        <div class="preview-body" v-html="renderSimpleMarkdown(previewItem.content || '')"></div>
      </div>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { useCollectorStore, type QueueItem } from '../stores/collector'
import { extract } from '../extractors'

const store = useCollectorStore()

// ── 预设 URL 分组 ────────────────────────────────────────────

interface PresetGroup {
  name: string
  urls: string[]
}

const DEFAULT_PRESETS: PresetGroup[] = [
  // 用户可通过「管理预设」添加已验证可自动采集的 URL 分组
]

const presetGroups = ref<PresetGroup[]>([])
const showPresetEditor = ref(false)
const editablePresets = ref<(PresetGroup & { urlsText: string })[]>([])

async function loadPresets() {
  try {
    const settings = await window.collector.getSettings()
    const saved = settings?.presetUrls
    presetGroups.value = saved?.length ? saved : DEFAULT_PRESETS
  } catch {
    presetGroups.value = DEFAULT_PRESETS
  }
}

function loadPreset(group: PresetGroup) {
  const existing = new Set(
    batchUrlsText.value
      .split('\n')
      .map(l => l.trim())
      .filter(Boolean)
  )
  const newUrls = group.urls.filter(u => !existing.has(u))
  if (!newUrls.length) {
    ElMessage.info('这些 URL 已在列表中')
    return
  }
  const prefix = batchUrlsText.value.trim() ? batchUrlsText.value.trim() + '\n' : ''
  batchUrlsText.value = prefix + newUrls.join('\n')
  ElMessage.success(`已添加 ${newUrls.length} 个 URL`)
}

function openPresetEditor() {
  editablePresets.value = presetGroups.value.map(g => ({
    ...g,
    urlsText: g.urls.join('\n'),
  }))
  showPresetEditor.value = true
}

async function savePresets() {
  const groups: PresetGroup[] = editablePresets.value
    .map(g => ({
      name: g.name.trim(),
      urls: g.urlsText
        .split('\n')
        .map(l => l.trim())
        .filter(l => l.startsWith('http')),
    }))
    .filter(g => g.name && g.urls.length)
  presetGroups.value = groups
  try {
    await window.collector.setSettings({ presetUrls: groups })
  } catch (e) {
    console.warn('Failed to save presets:', e)
  }
  showPresetEditor.value = false
  ElMessage.success('预设已保存')
}

// ── 内容预览 ────────────────────────────────────────────────

function retryItem(id: string) {
  store.retryQueueItem(id)
  ElMessage.info('已重置为待处理，下次采集时会重新提取')
}

function retryAllErrors() {
  const errorItems = store.queue.filter(i => i.status === 'error')
  errorItems.forEach(item => store.retryQueueItem(item.id))
  ElMessage.info(`已重置 ${errorItems.length} 个失败项`)
}

function openPreview(item: QueueItem) {
  previewItem.value = item
  showPreview.value = true
}

/** 简易 Markdown → HTML（仅用于预览展示） */
function renderSimpleMarkdown(text: string): string {
  let html = text
    .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  // 代码块
  html = html.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) =>
    `<pre><code class="lang-${lang}">${code}</code></pre>`)
  // 标题
  html = html.replace(/^###### (.+)$/gm, '<h6>$1</h6>')
  html = html.replace(/^##### (.+)$/gm, '<h5>$1</h5>')
  html = html.replace(/^#### (.+)$/gm, '<h4>$1</h4>')
  html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>')
  html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>')
  html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>')
  // 分割线
  html = html.replace(/^---+$/gm, '<hr/>')
  // 引用
  html = html.replace(/^> (.+)$/gm, '<blockquote>$1</blockquote>')
  // 行内样式
  html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
  html = html.replace(/_(.+?)_/g, '<em>$1</em>')
  html = html.replace(/`([^`]+)`/g, '<code>$1</code>')
  // 图片和链接
  html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/g,
    '<img src="$2" alt="$1" style="max-width:100%;border-radius:4px;margin:4px 0" />')
  html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank">$1</a>')
  // 列表
  html = html.replace(/^- (.+)$/gm, '<li>$1</li>')
  // 表格行
  html = html.replace(/^\|(.+)\|$/gm, (_, row) => {
    const cells = row.split('|').map((c: string) => c.trim())
    if (cells.every((c: string) => /^[-:]+$/.test(c))) return ''
    return '<tr>' + cells.map((c: string) => `<td>${c}</td>`).join('') + '</tr>'
  })
  // 段落和换行
  html = html.replace(/\n{2,}/g, '||PARA||')
  html = html.replace(/\n/g, '<br/>')
  html = html.replace(/\|\|PARA\|\|/g, '</p><p>')
  return '<p>' + html + '</p>'
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
function issueLabel(issue: string) {
  const map: Record<string, string> = {
    too_short: '内容过短', bad_title: '标题无效', truncated: '内容截断',
    blocked: '登录墙/验证码', images_missing: '图片缺失',
  }
  return map[issue] || issue
}

// ── refs ─────────────────────────────────────────────────────

const bgWebviewEl = ref<any>(null)    // 隐藏 webview，用于后台加载页面
const isProcessing = ref(false)
const isSyncing = ref(false)
const autoSave = ref(true)            // 采集后自动提交到知识库（默认开启）
const autoPoll = ref(false)           // 自动轮询后端任务队列
const showBatchDialog = ref(false)
const batchUrlsText = ref('')

// 内容预览
const showPreview = ref(false)
const previewItem = ref<QueueItem | null>(null)

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
  loadPresets()
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

      // ④ 自动保存（可选）+ Tier0 质检反馈环
      let savedDocId: string | undefined
      if (autoSave.value) {
        try {
          const saveResult = await store.saveCurrentPage({
            title: result.title,
            url: result.url,
            content: result.content,
            metadata: result.metadata,
          })
          savedDocId = saveResult.docId
          // 回写质检结果到队列项
          const qMeta = { ...(item.metadata || {}), quality: saveResult.quality }
          store.updateQueueItem(item.id, { docId: savedDocId, metadata: qMeta })

          // Tier0 质检未通过
          if (saveResult.quality?.action === 'blocked') {
            // 登录墙/验证码：重提取无意义，标记需要用户手动处理
            console.log('[Queue] Tier0 blocked for', item.url, saveResult.quality.issues)
            store.updateQueueItem(item.id, {
              error: '需要登录或验证码，请在浏览器中登录后重试',
              status: 'error',
            })
          } else if (saveResult.quality?.action === 're_extract') {
            console.log('[Queue] Tier0 re_extract signaled for', item.url, saveResult.quality.issues)
            try {
              const retry = await extract(bgWebviewEl.value, item.url)
              const retryResult = await store.saveCurrentPage({
                title: retry.title,
                url: retry.url,
                content: retry.content,
                metadata: retry.metadata,
              })
              // 记录 episode：原始提取 → 质检 → 重试
              await store.recordEpisode({
                url: item.url,
                kb_id: store.currentKbId,
                trigger: 'tier0_re_extract',
                first_quality: saveResult.quality,
                first_title: result.title,
                first_len: result.content?.length || 0,
                retry_title: retry.title,
                retry_len: retry.content?.length || 0,
                retry_quality: retryResult.quality,
                issues: saveResult.quality.issues,
              })
              if (retryResult.docId) {
                savedDocId = retryResult.docId
                const rqMeta = { ...(item.metadata || {}), quality: retryResult.quality }
                store.updateQueueItem(item.id, { docId: savedDocId, metadata: rqMeta })
              }
            } catch (retryErr: any) {
              console.warn('[Queue] re-extract failed for', item.url, retryErr.message)
            }
          }
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

  // 刷新知识库统计
  if (autoSave.value && successCount > 0) {
    await store.loadKbList()
  }

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
    const { saved, qualities } = await store.batchSave()
    await store.loadKbList()  // 刷新知识库统计
    const reExtractCount = qualities.filter(q => q.quality?.action === 're_extract').length
    if (reExtractCount > 0) {
      ElMessage.warning(`已保存 ${saved} 篇，其中 ${reExtractCount} 篇质检未通过（建议重新采集）`)
    } else {
      ElMessage.success(`已保存 ${saved} 篇文档到「${store.kbList.find(k => k.kb_id === store.currentKbId)?.name ?? store.currentKbId}」`)
    }
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

.preset-section {
  margin-bottom: 12px;
}
.preset-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}
.preset-groups {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.preset-editor {
  max-height: 400px;
  overflow-y: auto;
}
.preset-edit-item {
  margin-bottom: 12px;
  padding: 10px;
  background: var(--el-fill-color-lighter);
  border-radius: 6px;
}
.preset-edit-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.item-title.clickable {
  cursor: pointer;
}
.item-title.clickable:hover {
  color: var(--el-color-primary);
  text-decoration: underline;
}

.preview-content {
  padding: 0 4px;
}
.preview-meta {
  margin-bottom: 12px;
}
.preview-body {
  font-size: 14px;
  line-height: 1.8;
  color: var(--el-text-color-primary);
  word-break: break-word;
}
.preview-body :deep(h1),
.preview-body :deep(h2),
.preview-body :deep(h3) {
  margin: 16px 0 8px;
  font-weight: 600;
}
.preview-body :deep(code) {
  background: var(--el-fill-color-light);
  padding: 2px 6px;
  border-radius: 3px;
  font-size: 13px;
}
.preview-body :deep(img) {
  max-width: 100%;
  border-radius: 4px;
  margin: 4px 0;
}
.preview-body :deep(li) {
  margin-left: 16px;
  list-style: disc;
}
</style>
