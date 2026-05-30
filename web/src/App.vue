<template>
  <el-config-provider :locale="zhCn">
    <div class="app-layout">
      <!-- 顶部导航栏 -->
      <div class="app-header">
        <div class="header-left">
          <span class="logo" @click="router.push('/kb')">🔖 LLM Wiki</span>
        </div>

        <div class="header-center" v-if="currentKb">
          <router-link
            v-for="nav in navItems"
            :key="nav.path"
            :to="`/kb/${currentKbId}/${nav.path}`"
            class="nav-item"
            active-class="active"
          >
            {{ nav.label }}
          </router-link>
        </div>

        <div class="header-right">
          <!-- KB 切换 -->
          <el-select
            v-if="kbStore.kbList.length"
            v-model="kbStore.currentKbId"
            placeholder="选择知识库"
            size="small"
            style="width: 160px"
          >
            <el-option
              v-for="kb in kbStore.kbList"
              :key="kb.kb_id"
              :label="kb.name"
              :value="kb.kb_id"
            />
          </el-select>

          <!-- 全局搜索框 -->
          <el-input
            v-if="currentKb"
            v-model="globalQuery"
            placeholder="快速搜索..."
            size="small"
            style="width: 200px"
            @keyup.enter="goSearch"
          >
            <template #prefix><el-icon><Search /></el-icon></template>
          </el-input>
        </div>
      </div>

      <!-- 主内容 -->
      <div class="app-body">
        <!-- 侧边栏（Wiki 相关页面显示） -->
        <div class="app-sidebar" v-if="showSidebar">
          <app-sidebar />
        </div>
        <div class="app-main" :class="{ 'no-sidebar': !showSidebar }">
          <router-view />
        </div>
      </div>
    </div>
  </el-config-provider>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import { useKbStore } from './stores/kb'
import AppSidebar from './components/layout/AppSidebar.vue'

const router = useRouter()
const route = useRoute()
const kbStore = useKbStore()

const globalQuery = ref('')

const navItems = [
  { path: 'wiki', label: 'Wiki' },
  { path: 'search', label: '搜索' },
  { path: 'graph', label: '图谱' },
  { path: 'pipeline', label: '流水线' },
]

const currentKbId = computed(() => route.params.kbId as string || kbStore.currentKbId)
const currentKb = computed(() => kbStore.kbList.find(kb => kb.kb_id === currentKbId.value))
const showSidebar = computed(() => route.name === 'Wiki' || route.name === 'WikiPage')

function goSearch() {
  if (globalQuery.value && currentKbId.value) {
    router.push({ name: 'Search', params: { kbId: currentKbId.value }, query: { q: globalQuery.value } })
    globalQuery.value = ''
  }
}

// 同步 URL 中的 kbId 到 store
watch(() => route.params.kbId, (id) => {
  if (id) kbStore.setCurrentKb(id as string)
})

// KB 切换时同步导航到对应路由
watch(() => kbStore.currentKbId, (newId, oldId) => {
  if (!newId || newId === oldId) return
  // 如果当前在 KB 相关页面，切换到新 KB 的对应页面
  const currentPath = route.path
  if (currentPath.startsWith('/kb/') && oldId) {
    router.replace(currentPath.replace(`/kb/${oldId}/`, `/kb/${newId}/`))
  } else if (route.name === 'KBHome') {
    // 在首页选了 KB，跳到 Wiki 页
    router.push(`/kb/${newId}/wiki`)
  }
})

onMounted(async () => {
  await kbStore.loadKbList()
})
</script>

<style>
* { box-sizing: border-box; }
html, body { height: 100%; margin: 0; }
#app { height: 100%; }
</style>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
}

.app-header {
  display: flex;
  align-items: center;
  height: 56px;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color);
  padding: 0 20px;
  flex-shrink: 0;
  gap: 16px;
}

.logo {
  font-size: 18px;
  font-weight: 700;
  cursor: pointer;
  white-space: nowrap;
}

.header-center {
  flex: 1;
  display: flex;
  gap: 4px;
  justify-content: center;
}

.nav-item {
  padding: 6px 16px;
  border-radius: 6px;
  text-decoration: none;
  color: var(--el-text-color-secondary);
  font-size: 14px;
  transition: all 0.2s;
}
.nav-item:hover { background: var(--el-fill-color-light); color: var(--el-text-color-primary); }
.nav-item.active { background: var(--el-color-primary-light-9); color: var(--el-color-primary); font-weight: 500; }

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-left: auto;
}

.app-body {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.app-sidebar {
  width: 240px;
  flex-shrink: 0;
  border-right: 1px solid var(--el-border-color);
  overflow-y: auto;
}

.app-main {
  flex: 1;
  overflow: hidden;
}
.app-main.no-sidebar {
  flex: 1;
}
</style>
