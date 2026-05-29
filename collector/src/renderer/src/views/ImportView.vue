<template>
  <div class="import-view">
    <div class="content-wrapper">
      <h2>文件导入</h2>
      <p class="subtitle">支持 Markdown、TXT、PDF、HTML 格式</p>

      <!-- 拖拽上传区域 -->
      <div
        class="drop-zone"
        :class="{ dragging: isDragging }"
        @dragover.prevent="isDragging = true"
        @dragleave="isDragging = false"
        @drop.prevent="onDrop"
        @click="openFileDialog"
      >
        <el-icon class="drop-icon"><Upload /></el-icon>
        <p>拖拽文件到此处，或点击选择文件</p>
        <p class="hint">支持批量选择，每个文件将作为一篇原始文档导入</p>
      </div>

      <!-- 待导入文件列表 -->
      <div v-if="pendingFiles.length" class="file-list">
        <div class="file-list-header">
          <span>待导入文件（{{ pendingFiles.length }}）</span>
          <el-button type="primary" @click="importAll" :loading="isImporting">
            导入全部到「{{ currentKbName }}」
          </el-button>
        </div>
        <div v-for="(file, idx) in pendingFiles" :key="idx" class="file-item">
          <el-icon>
            <CircleCheck v-if="file.status === 'done'" style="color: var(--el-color-success)" />
            <CircleClose v-else-if="file.status === 'error'" style="color: var(--el-color-danger)" />
            <Loading v-else-if="file.status === 'processing'" class="rotating" />
            <Document v-else />
          </el-icon>
          <div class="file-info">
            <span class="file-name">{{ file.name }}</span>
            <span class="file-meta">{{ file.ext.toUpperCase() }} · {{ formatSize(file.size) }}</span>
            <span v-if="file.docId" class="file-doc-id">doc_id: {{ file.docId }}</span>
            <span v-if="file.error" class="file-error">{{ file.error }}</span>
          </div>
          <el-button
            size="small"
            text
            type="danger"
            @click="pendingFiles.splice(idx, 1)"
            :disabled="file.status === 'processing'"
          >
            移除
          </el-button>
        </div>
      </div>

      <!-- 说明 -->
      <el-alert
        title="关于本地文件导入"
        type="info"
        :closable="false"
        style="margin-top: 24px"
      >
        <template #default>
          <ul style="margin: 4px 0; padding-left: 16px;">
            <li>导入的文件将作为原始文档（raw）保存到知识库</li>
            <li>完成导入后，请前往 Web 界面的「流水线管理」处理这些文档</li>
            <li>处理后会自动提取实体/概念并建立 Wiki 知识图谱</li>
          </ul>
        </template>
      </el-alert>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { useCollectorStore } from '../stores/collector'

interface PendingFile {
  name: string
  path: string
  ext: string
  size: number
  status: 'pending' | 'processing' | 'done' | 'error'
  docId?: string
  error?: string
}

const store = useCollectorStore()
const pendingFiles = ref<PendingFile[]>([])
const isDragging = ref(false)
const isImporting = ref(false)

const currentKbName = computed(() => {
  const kb = store.kbList.find(k => k.kb_id === store.currentKbId)
  return kb?.name || '未选择知识库'
})

async function openFileDialog() {
  const paths = await window.collector.openFilesDialog()
  addFiles(paths)
}

function onDrop(e: DragEvent) {
  isDragging.value = false
  const files = Array.from(e.dataTransfer?.files || [])
  const paths = files.map(f => (f as any).path).filter(Boolean)
  addFiles(paths)
}

function addFiles(paths: string[]) {
  const supported = ['.md', '.txt', '.pdf', '.html', '.htm']
  for (const filePath of paths) {
    const name = filePath.split(/[/\\]/).pop() || filePath
    const ext = '.' + name.split('.').pop()?.toLowerCase()
    if (!supported.includes(ext)) continue

    // 避免重复添加
    if (pendingFiles.value.some(f => f.path === filePath)) continue

    pendingFiles.value.push({
      name,
      path: filePath,
      ext: ext.replace('.', ''),
      size: 0,
      status: 'pending',
    })
  }
}

async function importAll() {
  if (!store.currentKbId) {
    ElMessage.warning('请先选择知识库')
    return
  }

  const toImport = pendingFiles.value.filter(f => f.status === 'pending')
  if (!toImport.length) {
    ElMessage.info('没有待导入的文件')
    return
  }

  isImporting.value = true
  let success = 0

  for (const file of toImport) {
    const idx = pendingFiles.value.findIndex(f => f.path === file.path)
    pendingFiles.value[idx].status = 'processing'

    try {
      const result = await window.collector.uploadFile(store.currentKbId, file.path)
      pendingFiles.value[idx].status = 'done'
      pendingFiles.value[idx].docId = result.doc_id
      success++
    } catch (e: any) {
      pendingFiles.value[idx].status = 'error'
      pendingFiles.value[idx].error = e.message
    }
  }

  isImporting.value = false
  ElMessage.success(`导入完成：${success}/${toImport.length} 个文件成功`)
}

function formatSize(bytes: number): string {
  if (!bytes) return '—'
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`
}
</script>

<style scoped>
.import-view {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}
.content-wrapper {
  max-width: 680px;
  margin: 0 auto;
}
h2 { margin-top: 0; }
.subtitle {
  color: var(--el-text-color-secondary);
  margin-bottom: 20px;
}

.drop-zone {
  border: 2px dashed var(--el-border-color);
  border-radius: 12px;
  padding: 48px 24px;
  text-align: center;
  cursor: pointer;
  transition: all 0.2s;
  background: var(--el-fill-color-lighter);
}
.drop-zone:hover, .drop-zone.dragging {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}
.drop-icon {
  font-size: 48px;
  color: var(--el-text-color-placeholder);
  margin-bottom: 8px;
}
.hint { font-size: 12px; color: var(--el-text-color-secondary); margin: 0; }

.file-list {
  margin-top: 20px;
  border: 1px solid var(--el-border-color);
  border-radius: 8px;
  overflow: hidden;
}
.file-list-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 14px;
  background: var(--el-fill-color);
  font-size: 13px;
  font-weight: 500;
}
.file-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 14px;
  border-top: 1px solid var(--el-border-color-lighter);
}
.file-info {
  flex: 1;
  min-width: 0;
}
.file-name {
  display: block;
  font-size: 13px;
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.file-meta {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.file-doc-id {
  display: block;
  font-size: 11px;
  color: var(--el-color-success);
  font-family: monospace;
}
.file-error {
  display: block;
  font-size: 11px;
  color: var(--el-color-danger);
}

.rotating {
  animation: rotate 1s linear infinite;
}
@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
