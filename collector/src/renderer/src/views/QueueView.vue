<template>
  <div class="queue-view">
    <!-- 工具栏 -->
    <div class="toolbar">
      <span class="title">采集队列</span>
      <el-space>
        <el-button size="small" @click="addBatchUrls" type="primary">
          <el-icon><Plus /></el-icon> 批量添加 URL
        </el-button>
        <el-button size="small" @click="processQueue" :loading="isProcessing" :disabled="!store.pendingCount">
          <el-icon><VideoPlay /></el-icon> 开始采集（{{ store.pendingCount }}）
        </el-button>
        <el-button size="small" @click="saveAllDone" :disabled="!unsavedDoneItems.length">
          <el-icon><Upload /></el-icon> 批量保存（{{ unsavedDoneItems.length }}）
        </el-button>
        <el-button size="small" @click="store.clearQueue()">
          <el-icon><Delete /></el-icon> 清除已完成
        </el-button>
      </el-space>
    </div>

    <!-- 统计 -->
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
        <div class="item-url">{{ item.url }}</div>
        <div class="item-error" v-if="item.error">{{ item.error }}</div>
      </div>
    </div>

    <el-empty v-else description="队列为空，去浏览页面采集内容吧" />

    <!-- 批量添加 URL 对话框 -->
    <el-dialog v-model="showBatchDialog" title="批量添加 URL" width="560px">
      <p style="margin-top: 0; color: var(--el-text-color-secondary)">每行一个 URL</p>
      <el-input
        v-model="batchUrlsText"
        type="textarea"
        :rows="10"
        placeholder="https://www.xiaohongshu.com/explore/...&#10;https://zhihu.com/question/...&#10;..."
      />
      <template #footer>
        <el-button @click="showBatchDialog = false">取消</el-button>
        <el-button type="primary" @click="confirmBatchAdd">
          添加 {{ batchUrlCount }} 个 URL
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useCollectorStore } from '../stores/collector'

const store = useCollectorStore()
const isProcessing = ref(false)
const showBatchDialog = ref(false)
const batchUrlsText = ref('')

const doneCount = computed(() => store.queue.filter(i => i.status === 'done').length)
const savedCount = computed(() => store.queue.filter(i => i.docId).length)
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

function addBatchUrls() {
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

async function processQueue() {
  if (!store.currentKbId) {
    ElMessage.warning('请先选择知识库')
    return
  }

  isProcessing.value = true
  const pendingItems = store.queue.filter(i => i.status === 'pending')

  for (const item of pendingItems) {
    store.updateQueueItem(item.id, { status: 'processing' })

    try {
      // 通过 IPC 让主进程打开此 URL 并提取内容
      // 这里简化实现：直接用 fetch 尝试获取（实际应通过主进程 webContents）
      // 完整实现需要在主进程创建一个隐藏的 BrowserWindow 来访问页面
      await new Promise(r => setTimeout(r, 1000)) // 模拟延迟

      // TODO: 接入真实的主进程批量采集逻辑
      // const result = await window.collector.crawlUrl(item.url)
      // store.updateQueueItem(item.id, { status: 'done', title: result.title, content: result.content })

      store.updateQueueItem(item.id, {
        status: 'done',
        title: `页面：${new URL(item.url).hostname}`,
        content: `从 ${item.url} 采集的内容（请在浏览器模式下手动保存以获取完整内容）`,
      })
    } catch (e: any) {
      store.updateQueueItem(item.id, { status: 'error', error: e.message })
    }
  }

  isProcessing.value = false
  ElMessage.success('批量采集完成')
}

async function saveAllDone() {
  if (!store.currentKbId) {
    ElMessage.warning('请先选择知识库')
    return
  }

  try {
    await store.batchSave()
    ElMessage.success(`已保存 ${unsavedDoneItems.value.length} 篇文档`)
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
}
.toolbar .title {
  font-size: 15px;
  font-weight: 600;
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
}
.queue-item.done { border-left: 3px solid var(--el-color-success); }
.queue-item.error { border-left: 3px solid var(--el-color-danger); }
.queue-item.processing { border-left: 3px solid var(--el-color-warning); }
.queue-item.pending { border-left: 3px solid var(--el-border-color); }

.item-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}
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
  to { transform: rotate(360deg); }
}
</style>
