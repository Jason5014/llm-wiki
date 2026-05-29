<template>
  <div class="settings-view">
    <div class="content-wrapper">
      <h2>设置</h2>

      <el-card class="settings-card">
        <template #header>后端连接</template>
        <el-form label-width="140px" label-position="left">
          <el-form-item label="API 地址">
            <el-input v-model="store.apiBaseUrl" placeholder="http://localhost:8765">
              <template #append>
                <el-button @click="testConnection" :loading="testing">测试连接</el-button>
              </template>
            </el-input>
            <div class="form-tip">FastAPI 后端的地址，默认 http://localhost:8765</div>
          </el-form-item>
          <el-form-item>
            <el-button type="primary" @click="saveSettings">保存设置</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <el-card class="settings-card">
        <template #header>登录状态管理</template>
        <p style="color: var(--el-text-color-secondary); margin-top: 0">
          内嵌浏览器使用独立的持久化 Session（persist:wiki-collector），
          登录 Cookie 会自动保存，应用重启后保持登录状态。
        </p>

        <el-table :data="cookieSummary" style="margin-bottom: 12px">
          <el-table-column prop="domain" label="已登录网站" />
          <el-table-column prop="count" label="Cookie 数量" width="120" align="right" />
          <el-table-column label="操作" width="100" align="center">
            <template #default="{ row }">
              <el-button text type="danger" size="small" @click="clearDomain(row.domain)">
                退出
              </el-button>
            </template>
          </el-table-column>
        </el-table>

        <el-button @click="loadCookies" size="small">刷新</el-button>
        <el-popconfirm title="确定清除所有登录状态？" @confirm="clearAllCookies">
          <template #reference>
            <el-button size="small" type="danger">清除所有登录状态</el-button>
          </template>
        </el-popconfirm>
      </el-card>

      <el-card class="settings-card">
        <template #header>版本信息</template>
        <el-descriptions :column="1" border>
          <el-descriptions-item label="应用版本">0.1.0</el-descriptions-item>
          <el-descriptions-item label="Electron 版本">{{ electronVersion }}</el-descriptions-item>
          <el-descriptions-item label="Session">persist:wiki-collector</el-descriptions-item>
        </el-descriptions>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useCollectorStore } from '../stores/collector'

const store = useCollectorStore()
const testing = ref(false)
const cookies = ref<any[]>([])
const electronVersion = ref('N/A')

const cookieSummary = computed(() => {
  const map: Record<string, number> = {}
  for (const cookie of cookies.value) {
    const domain = cookie.domain?.replace(/^\./, '')
    if (domain) {
      map[domain] = (map[domain] || 0) + 1
    }
  }
  return Object.entries(map)
    .sort((a, b) => b[1] - a[1])
    .map(([domain, count]) => ({ domain, count }))
})

async function testConnection() {
  testing.value = true
  try {
    const resp = await fetch(`${store.apiBaseUrl}/health`)
    if (resp.ok) {
      ElMessage.success('✅ 后端连接正常')
    } else {
      ElMessage.error(`连接失败：HTTP ${resp.status}`)
    }
  } catch (e: any) {
    ElMessage.error(`无法连接：${e.message}`)
  } finally {
    testing.value = false
  }
}

async function saveSettings() {
  await store.saveSettings()
  ElMessage.success('设置已保存')
}

async function loadCookies() {
  try {
    const all = await window.collector.getAllCookies()
    cookies.value = all as any[]
  } catch (e) {
    console.error(e)
  }
}

async function clearDomain(domain: string) {
  await window.collector.clearCookies(domain)
  await loadCookies()
  ElMessage.success(`已清除 ${domain} 的登录状态`)
}

async function clearAllCookies() {
  await window.collector.clearCookies()
  await loadCookies()
  ElMessage.success('已清除所有登录状态')
}

onMounted(() => {
  loadCookies()
})
</script>

<style scoped>
.settings-view {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}
.content-wrapper {
  max-width: 680px;
  margin: 0 auto;
}
h2 { margin-top: 0; }
.settings-card {
  margin-bottom: 20px;
}
.form-tip {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
</style>
