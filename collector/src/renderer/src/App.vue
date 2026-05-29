<template>
  <div class="app-container">
    <!-- 顶部工具栏 -->
    <div class="toolbar titlebar-drag">
      <!-- macOS 红绿灯占位 -->
      <div class="traffic-light-space" v-if="isMac" />

      <!-- 导航标签 -->
      <div class="nav-tabs titlebar-no-drag">
        <div
          v-for="tab in tabs"
          :key="tab.path"
          class="nav-tab"
          :class="{ active: currentPath === tab.path }"
          @click="router.push(tab.path)"
        >
          <el-icon><component :is="tab.icon" /></el-icon>
          <span>{{ tab.label }}</span>
        </div>
      </div>

      <!-- 知识库选择 + 新建 -->
      <div class="kb-selector titlebar-no-drag">
        <el-select
          v-model="store.currentKbId"
          placeholder="选择知识库"
          size="small"
          style="width: 160px"
          @change="store.saveSettings"
        >
          <el-option
            v-for="kb in store.kbList"
            :key="kb.kb_id"
            :label="kb.name"
            :value="kb.kb_id"
          />
        </el-select>
        <el-button size="small" :icon="Plus" circle title="新建知识库" @click="showCreateKb = true" />
      </div>

      <!-- 新建知识库弹框 -->
      <el-dialog v-model="showCreateKb" title="新建知识库" width="400px" :close-on-click-modal="false">
        <el-form :model="createKbForm" label-width="80px" label-position="left" @submit.prevent>
          <el-form-item label="名称" required>
            <el-input v-model="createKbForm.name" placeholder="AI 技术知识库" />
          </el-form-item>
          <el-form-item label="领域">
            <el-input v-model="createKbForm.domain" placeholder="AI/Tech（可选）" />
          </el-form-item>
          <el-form-item label="简介">
            <el-input v-model="createKbForm.description" type="textarea" :rows="2" placeholder="可选" />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showCreateKb = false">取消</el-button>
          <el-button type="primary" :loading="creatingKb" @click="confirmCreateKb">创建</el-button>
        </template>
      </el-dialog>

      <!-- 队列计数 -->
      <div class="queue-badge titlebar-no-drag">
        <el-badge :value="store.pendingCount" :hidden="store.pendingCount === 0" type="warning">
          <el-button size="small" circle @click="router.push('/queue')">
            <el-icon><List /></el-icon>
          </el-button>
        </el-badge>
      </div>
    </div>

    <!-- 主内容区 -->
    <div class="main-content">
      <router-view class="route-content" />
    </div>

    <!-- 底部状态栏 -->
    <div class="status-bar">
      <span>知识库：{{ currentKbName }}</span>
      <span style="margin-left: 16px">已采集：{{ store.doneCount }} 篇</span>
      <span style="margin-left: auto; color: var(--el-color-success)" v-if="connected">
        ● 后端已连接
      </span>
      <span style="margin-left: auto; color: var(--el-color-danger)" v-else>
        ● 后端未连接
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { useCollectorStore } from './stores/collector'

const router = useRouter()
const route = useRoute()
const store = useCollectorStore()

const connected = ref(false)
const isMac = navigator.platform.toLowerCase().includes('mac')

// 新建知识库
const showCreateKb = ref(false)
const creatingKb = ref(false)
const createKbForm = ref({ name: '', domain: '', description: '' })

async function confirmCreateKb() {
  if (!createKbForm.value.name.trim()) {
    ElMessage.warning('请填写知识库名称')
    return
  }
  creatingKb.value = true
  try {
    await store.createKb(createKbForm.value)
    showCreateKb.value = false
    createKbForm.value = { name: '', domain: '', description: '' }
    ElMessage.success('知识库创建成功，已自动切换')
  } catch (e: any) {
    ElMessage.error(e?.response?.data?.detail || e?.message || '创建失败')
  } finally {
    creatingKb.value = false
  }
}

const tabs = [
  { path: '/browser', label: '浏览采集', icon: 'Monitor' },
  { path: '/queue', label: '采集队列', icon: 'List' },
  { path: '/import', label: '文件导入', icon: 'Upload' },
  { path: '/settings', label: '设置', icon: 'Setting' },
]

const currentPath = computed(() => route.path)
const currentKbName = computed(() => {
  const kb = store.kbList.find(k => k.kb_id === store.currentKbId)
  return kb?.name || '未选择'
})

// 检查后端连接
async function checkConnection() {
  try {
    await fetch(`${store.apiBaseUrl}/health`)
    connected.value = true
  } catch {
    connected.value = false
  }
}

onMounted(async () => {
  await store.loadSettings()
  await store.loadKbList()
  await checkConnection()
  // 定期检查连接
  setInterval(checkConnection, 10000)
})
</script>

<style>
html, body, #app {
  height: 100%;
  margin: 0;
}
</style>

<style scoped>
.app-container {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background: var(--el-bg-color-page);
}

.toolbar {
  display: flex;
  align-items: center;
  height: var(--toolbar-height, 52px);
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color);
  padding: 0 12px;
  gap: 8px;
  flex-shrink: 0;
}

.traffic-light-space {
  width: 70px;
  flex-shrink: 0;
}

.nav-tabs {
  display: flex;
  gap: 4px;
  flex: 1;
}

.nav-tab {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: var(--el-text-color-secondary);
  transition: all 0.2s;
}
.nav-tab:hover {
  background: var(--el-fill-color-light);
  color: var(--el-text-color-primary);
}
.nav-tab.active {
  background: var(--el-color-primary-light-9);
  color: var(--el-color-primary);
  font-weight: 500;
}

.kb-selector {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}
.queue-badge {
  flex-shrink: 0;
}

.main-content {
  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

/* router-view 渲染的组件需要作为 flex 子项填满 main-content */
.main-content :deep(.route-content) {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
</style>
