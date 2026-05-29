<template>
  <div class="home-view">
    <div class="home-header">
      <h2>我的知识库</h2>
      <el-button type="primary" @click="showCreate = true">
        <el-icon><Plus /></el-icon> 创建知识库
      </el-button>
    </div>

    <!-- KB 卡片网格 -->
    <div class="kb-grid" v-if="kbStore.kbList.length">
      <el-card
        v-for="kb in kbStore.kbList"
        :key="kb.kb_id"
        class="kb-card"
        :body-style="{ padding: '0' }"
      >
        <div class="kb-card-body">
          <div class="kb-icon">📚</div>
          <div class="kb-info">
            <div class="kb-name">{{ kb.name }}</div>
            <div class="kb-id">{{ kb.kb_id }}</div>
            <div class="kb-desc" v-if="kb.description">{{ kb.description }}</div>
          <div class="kb-tags" v-if="kb.domain?.length">
            <el-tag v-for="tag in kb.domain" :key="tag" size="small" type="info" style="margin-right:4px">{{ tag }}</el-tag>
          </div>
          </div>
          <div class="kb-stats">
            <div class="stat">
              <span class="stat-value">{{ kb.stats?.raw_count || 0 }}</span>
              <span class="stat-label">文档</span>
            </div>
            <div class="stat">
              <span class="stat-value">{{ kb.stats?.entity_count || 0 }}</span>
              <span class="stat-label">实体</span>
            </div>
            <div class="stat">
              <span class="stat-value">{{ kb.stats?.concept_count || 0 }}</span>
              <span class="stat-label">概念</span>
            </div>
          </div>
          <div class="kb-status">
            <el-tag :type="kb.stats?.indexed ? 'success' : 'warning'" size="small">
              {{ kb.stats?.indexed ? '已索引' : '未索引' }}
            </el-tag>
          </div>
          <div class="kb-actions">
            <el-button size="small" type="primary" @click="browseKb(kb.kb_id)">浏览</el-button>
            <el-button size="small" @click="processKb(kb.kb_id)">处理</el-button>
            <el-button size="small" type="danger" text @click="deleteKb(kb.kb_id)">删除</el-button>
          </div>
        </div>
      </el-card>

      <!-- 新建卡片 -->
      <div class="kb-card-new" @click="showCreate = true">
        <el-icon class="new-icon"><Plus /></el-icon>
        <span>新建知识库</span>
      </div>
    </div>

    <!-- 空状态 -->
    <el-empty v-else description="暂无知识库，创建第一个吧" />

    <!-- 创建对话框 -->
    <el-dialog v-model="showCreate" title="创建知识库" width="480px">
      <el-form :model="createForm" label-width="100px" label-position="left">
        <el-form-item label="知识库 ID" required>
          <el-input v-model="createForm.kb_id" placeholder="ai-tech（字母/数字/连字符）" />
          <div class="form-tip">唯一标识，创建后不可修改</div>
        </el-form-item>
        <el-form-item label="显示名称" required>
          <el-input v-model="createForm.name" placeholder="AI 技术知识库" />
        </el-form-item>
        <el-form-item label="领域标签">
          <el-select
            v-model="createForm.domain"
            multiple
            filterable
            allow-create
            default-first-option
            placeholder="输入后回车添加标签"
            style="width:100%"
          >
            <el-option v-for="tag in domainPresets" :key="tag" :label="tag" :value="tag" />
          </el-select>
        </el-form-item>
        <el-form-item label="简介">
          <el-input v-model="createForm.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreate = false">取消</el-button>
        <el-button type="primary" @click="confirmCreate" :loading="creating">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useKbStore } from '../stores/kb'

const router = useRouter()
const kbStore = useKbStore()

const showCreate = ref(false)
const creating = ref(false)
const createForm = ref<{ kb_id: string; name: string; domain: string[]; description: string }>({
  kb_id: '', name: '', domain: [], description: '',
})

const domainPresets = [
  'AI', '机器学习', '深度学习', 'LLM', 'RAG',
  '前端', '后端', '全栈', '算法', '数据分析',
  '产品', '设计', '运营', '财经', '法律',
]

function browseKb(kbId: string) {
  router.push({ name: 'Wiki', params: { kbId } })
}

function processKb(kbId: string) {
  router.push({ name: 'Pipeline', params: { kbId } })
}

async function deleteKb(kbId: string) {
  await ElMessageBox.confirm(`确定删除知识库 "${kbId}"？此操作不可撤销。`, '确认删除', {
    type: 'warning',
    confirmButtonText: '确定删除',
    confirmButtonClass: 'el-button--danger',
  })
  await kbStore.deleteKb(kbId)
  ElMessage.success('已删除')
}

async function confirmCreate() {
  if (!createForm.value.kb_id || !createForm.value.name) {
    ElMessage.warning('请填写知识库 ID 和名称')
    return
  }
  creating.value = true
  try {
    const kb = await kbStore.createKb(createForm.value)
    showCreate.value = false
    createForm.value = { kb_id: '', name: '', domain: [], description: '' }
    ElMessage.success(`知识库 "${kb.name}" 创建成功`)
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || '创建失败')
  } finally {
    creating.value = false
  }
}
</script>

<style scoped>
.home-view { padding: 24px; height: 100%; overflow-y: auto; }
.home-header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 24px; }
.home-header h2 { margin: 0; font-size: 22px; }

.kb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 16px;
}

.kb-card { cursor: pointer; transition: box-shadow 0.2s; }
.kb-card:hover { box-shadow: 0 4px 16px rgba(0,0,0,0.12); }
.kb-card-body { padding: 20px; display: flex; flex-direction: column; gap: 12px; }

.kb-icon { font-size: 32px; }
.kb-info { }
.kb-name { font-size: 16px; font-weight: 600; margin-bottom: 2px; }
.kb-id { font-size: 12px; color: var(--el-text-color-secondary); font-family: monospace; }
.kb-desc { font-size: 13px; color: var(--el-text-color-secondary); margin-top: 4px; }

.kb-stats { display: flex; gap: 16px; }
.stat { display: flex; flex-direction: column; align-items: center; }
.stat-value { font-size: 20px; font-weight: 700; color: var(--el-color-primary); }
.stat-label { font-size: 11px; color: var(--el-text-color-secondary); }

.kb-actions { display: flex; gap: 8px; }

.kb-card-new {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  border: 2px dashed var(--el-border-color);
  border-radius: 8px;
  padding: 40px;
  cursor: pointer;
  color: var(--el-text-color-secondary);
  font-size: 14px;
  transition: all 0.2s;
  min-height: 200px;
}
.kb-card-new:hover { border-color: var(--el-color-primary); color: var(--el-color-primary); }
.new-icon { font-size: 32px; }

.form-tip { font-size: 12px; color: var(--el-text-color-secondary); margin-top: 4px; }
</style>
