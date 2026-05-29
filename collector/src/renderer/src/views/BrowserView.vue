<template>
  <div class="browser-view">
    <!-- 地址栏工具栏 -->
    <div class="address-bar">
      <el-button-group size="small">
        <el-button @click="webviewEl?.goBack()" :disabled="!canGoBack">
          <el-icon><ArrowLeft /></el-icon>
        </el-button>
        <el-button @click="webviewEl?.goForward()" :disabled="!canGoForward">
          <el-icon><ArrowRight /></el-icon>
        </el-button>
        <el-button @click="webviewEl?.reload()">
          <el-icon><Refresh /></el-icon>
        </el-button>
      </el-button-group>

      <el-input
        v-model="addressInput"
        class="url-input"
        placeholder="输入网址..."
        @keyup.enter="navigate"
        size="small"
      >
        <template #prefix>
          <el-icon v-if="isLoading"><Loading /></el-icon>
          <el-icon v-else><Link /></el-icon>
        </template>
      </el-input>

      <!-- 保存当前页 -->
      <el-button
        type="primary"
        size="small"
        @click="saveCurrentPage"
        :loading="isSaving"
      >
        <el-icon><Download /></el-icon>
        保存当前页
      </el-button>

      <!-- 快速跳转常用网站 -->
      <el-dropdown size="small" trigger="click">
        <el-button size="small">
          常用网站 <el-icon class="el-icon--right"><ArrowDown /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item
              v-for="site in quickSites"
              :key="site.url"
              @click="goTo(site.url)"
            >
              {{ site.name }}
            </el-dropdown-item>
          </el-dropdown-menu>
        </template>
      </el-dropdown>
    </div>

    <!-- 内嵌浏览器容器：用 position: relative 包裹，让 webview 绝对定位铺满 -->
    <!-- webview 是 Electron 特殊元素，flex: 1 无法可靠撑高，需要 absolute 布局 -->
    <div class="webview-container">
      <webview
        ref="webviewEl"
        class="browser-webview"
        :src="currentUrl"
        partition="persist:wiki-collector"
        allowpopups
        webpreferences="contextIsolation=false"
        @did-start-loading="isLoading = true"
        @did-stop-loading="onStopLoading"
        @did-navigate="onNavigate"
        @did-navigate-in-page="onNavigate"
        @page-title-updated="onTitleUpdated"
      />
    </div>

    <!-- 保存预览弹窗 -->
    <el-dialog
      v-model="showPreview"
      title="预览并确认保存"
      width="640px"
      :close-on-click-modal="false"
    >
      <div class="preview-content">
        <el-form label-width="80px" label-position="left">
          <el-form-item label="标题">
            <el-input v-model="previewData.title" />
          </el-form-item>
          <el-form-item label="来源 URL">
            <el-input v-model="previewData.url" disabled />
          </el-form-item>
          <el-form-item label="内容预览">
            <el-input
              v-model="previewData.contentPreview"
              type="textarea"
              :rows="8"
              placeholder="正文内容..."
            />
          </el-form-item>
        </el-form>
      </div>
      <template #footer>
        <el-button @click="showPreview = false">取消</el-button>
        <el-button type="primary" @click="confirmSave" :loading="isSaving">
          确认保存到「{{ currentKbName }}」
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useCollectorStore } from '../stores/collector'

const store = useCollectorStore()
const webviewEl = ref<any>(null)

const addressInput = ref('https://www.google.com')
const currentUrl = ref('https://www.google.com')
const isLoading = ref(false)
const isSaving = ref(false)
const canGoBack = ref(false)
const canGoForward = ref(false)

const showPreview = ref(false)
const previewData = ref({
  title: '',
  url: '',
  content: '',
  contentPreview: '',
  metadata: {} as Record<string, unknown>,
})

const quickSites = [
  { name: '小红书', url: 'https://www.xiaohongshu.com' },
  { name: '知乎', url: 'https://www.zhihu.com' },
  { name: '微信公众号', url: 'https://mp.weixin.qq.com' },
  { name: '少数派', url: 'https://sspai.com' },
  { name: 'GitHub', url: 'https://github.com' },
]

const currentKbName = computed(() => {
  const kb = store.kbList.find(k => k.kb_id === store.currentKbId)
  return kb?.name || '未选择知识库'
})

function navigate() {
  let url = addressInput.value.trim()
  if (!url.startsWith('http://') && !url.startsWith('https://')) {
    // 如果不是 URL，当作搜索词
    if (!url.includes('.')) {
      url = `https://www.google.com/search?q=${encodeURIComponent(url)}`
    } else {
      url = `https://${url}`
    }
  }
  currentUrl.value = url
}

function goTo(url: string) {
  addressInput.value = url
  currentUrl.value = url
}

function onStopLoading() {
  isLoading.value = false
  if (webviewEl.value) {
    addressInput.value = webviewEl.value.getURL?.() || addressInput.value
    canGoBack.value = webviewEl.value.canGoBack?.() ?? false
    canGoForward.value = webviewEl.value.canGoForward?.() ?? false
  }
}

function onNavigate(event: any) {
  addressInput.value = event.url || ''
}

function onTitleUpdated(event: any) {
  // 可用于 UI 显示当前页标题
}

async function saveCurrentPage() {
  if (!store.currentKbId) {
    ElMessage.warning('请先选择知识库')
    return
  }
  if (!webviewEl.value) return

  isSaving.value = true
  try {
    // 通过 webview 执行 JS 提取内容
    const result = await extractContentFromWebview()
    previewData.value = {
      title: result.title,
      url: result.url,
      content: result.content,
      contentPreview: result.content.slice(0, 2000),
      metadata: result.metadata,
    }
    showPreview.value = true
  } catch (e: any) {
    ElMessage.error(`提取内容失败：${e.message}`)
  } finally {
    isSaving.value = false
  }
}

async function extractContentFromWebview(): Promise<{
  title: string; url: string; content: string; metadata: Record<string, unknown>
}> {
  const url = webviewEl.value.getURL()
  const hostname = new URL(url).hostname

  let result: any

  if (hostname.includes('xiaohongshu.com')) {
    result = await webviewEl.value.executeJavaScript(`
      (function() {
        const title = document.querySelector('#detail-title')?.textContent?.trim()
          || document.querySelector('.title')?.textContent?.trim()
          || document.title;
        const contentEl = document.querySelector('#detail-desc') || document.querySelector('.desc');
        const content = contentEl?.textContent?.trim() || '';
        const likes = document.querySelector('.like-wrapper .count')?.textContent?.trim() || '0';
        const collects = document.querySelector('.collect-wrapper .count')?.textContent?.trim() || '0';
        return { title, content, metadata: { likes, collects, source: 'xiaohongshu' } };
      })()
    `)
  } else if (hostname.includes('zhihu.com')) {
    result = await webviewEl.value.executeJavaScript(`
      (function() {
        // ── 优先检测是否有弹框 Modal 打开 ──────────────────────────
        // 知乎首页点击文章卡片会出现 Modal 预览，需要从弹框内取内容和真实 URL
        const modal = document.querySelector('.Modal--default, .Modal-content, [class*="ContentModal"]');
        if (modal) {
          // 弹框内的标题（文章 or 问答）
          const modalTitle =
            modal.querySelector('.Post-Title, .QuestionHeader-title, .ContentItem-title')?.textContent?.trim()
            || modal.querySelector('h1, h2')?.textContent?.trim()
            || document.title;
          // 弹框内的正文
          const modalContent =
            Array.from(modal.querySelectorAll('.RichText.ztext, .Post-RichTextContainer'))
              .map(e => e.textContent?.trim()).filter(Boolean).join('\\n\\n---\\n\\n')
            || modal.innerText?.replace(/\\n{3,}/g, '\\n\\n').trim() || '';
          // 尝试从弹框内找到文章的真实链接
          const canonicalLink =
            modal.querySelector('a[href*="/p/"], a[href*="/question/"]')?.href
            || document.querySelector('link[rel="canonical"]')?.href
            || location.href;
          return {
            title: modalTitle,
            content: modalContent,
            canonicalUrl: canonicalLink,
            metadata: { source: 'zhihu', via: 'modal' }
          };
        }

        // ── 普通页面（文章 / 问答）───────────────────────────────
        const isArticle = location.pathname.startsWith('/p/');
        const title = isArticle
          ? document.querySelector('.Post-Title')?.textContent?.trim()
          : document.querySelector('.QuestionHeader-title')?.textContent?.trim();
        const content = isArticle
          ? document.querySelector('.Post-RichTextContainer')?.textContent?.trim()
          : Array.from(document.querySelectorAll('.RichText.ztext'))
              .map(e => e.textContent?.trim()).join('\\n\\n---\\n\\n');
        return {
          title: title || document.title,
          content: content || '',
          canonicalUrl: null,
          metadata: { source: 'zhihu' }
        };
      })()
    `)
  } else {
    result = await webviewEl.value.executeJavaScript(`
      (function() {
        const mainEl = document.querySelector('main, article, [role="main"], .post-content, .article-content')
          || document.body;
        const text = mainEl?.innerText?.replace(/\\n{3,}/g, '\\n\\n').trim() || '';
        return { title: document.title, content: text.substring(0, 10000), metadata: { source: 'web' } };
      })()
    `)
  }

  // 弹框场景：使用从 DOM 中提取的真实文章 URL，而非 webview 当前的页面 URL
  const finalUrl = result.canonicalUrl || url

  return {
    title: result.title || finalUrl,
    url: finalUrl,
    content: result.content || '',
    metadata: result.metadata || {},
  }
}

async function confirmSave() {
  if (!store.currentKbId) {
    ElMessage.warning('请先选择知识库')
    return
  }

  isSaving.value = true
  try {
    const docId = await store.saveCurrentPage({
      title: previewData.value.title,
      url: previewData.value.url,
      content: previewData.value.content,
      metadata: previewData.value.metadata,
    })
    showPreview.value = false
    ElMessage.success(`✅ 已保存，doc_id: ${docId}`)
  } catch (e: any) {
    ElMessage.error(`保存失败：${e.message}`)
  } finally {
    isSaving.value = false
  }
}

onMounted(() => {
  // webview ready 事件
  if (webviewEl.value) {
    webviewEl.value.addEventListener?.('dom-ready', () => {
      canGoBack.value = webviewEl.value?.canGoBack() ?? false
      canGoForward.value = webviewEl.value?.canGoForward() ?? false
    })
  }
})
</script>

<style scoped>
.browser-view {
  display: flex;
  flex-direction: column;
  flex: 1;          /* 作为 main-content 的 flex 子项，比 height:100% 更可靠 */
  overflow: hidden;
}

.address-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  background: var(--el-bg-color);
  border-bottom: 1px solid var(--el-border-color);
  flex-shrink: 0;
}

.url-input {
  flex: 1;
}

/* webview 容器：flex: 1 撑满剩余高度，relative 定位给 webview 提供锚点 */
.webview-container {
  flex: 1;
  position: relative;
  overflow: hidden;
}

/* webview 绝对定位铺满容器 —— 这是让 Electron webview 可靠填充高度的标准方式 */
.browser-webview {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  border: none;
}

.preview-content {
  max-height: 60vh;
  overflow-y: auto;
}
</style>
