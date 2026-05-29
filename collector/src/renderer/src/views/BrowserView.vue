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

      <!-- 诊断：分析页面 DOM 结构（仅开发模式可见） -->
      <el-button v-if="isDev" size="small" @click="diagnosePage" :loading="isDiagnosing">
        诊断
      </el-button>

      <!-- 书签 -->
      <el-dropdown size="small" trigger="click">
        <el-button size="small">
          书签 <el-icon class="el-icon--right"><ArrowDown /></el-icon>
        </el-button>
        <template #dropdown>
          <el-dropdown-menu>
            <el-dropdown-item
              v-for="bm in bookmarks"
              :key="bm.url"
              @click="goTo(bm.url)"
            >
              {{ bm.name }}
            </el-dropdown-item>
            <el-dropdown-item divided @click="addBookmark">添加当前页</el-dropdown-item>
            <el-dropdown-item @click="showBookmarkMgr = true">管理书签</el-dropdown-item>
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
        @did-start-loading="onStartLoading"
        @did-stop-loading="onStopLoading"
        @did-finish-load="onStopLoading"
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
          <!-- 元数据展示 -->
          <template v-if="previewData.metadata?.author || previewData.metadata?.date">
            <el-form-item v-if="previewData.metadata?.author" label="作者">
              <span>{{ previewData.metadata.author }}</span>
              <span v-if="previewData.metadata?.authorBio" style="color: var(--el-text-color-secondary); margin-left: 8px;">{{ previewData.metadata.authorBio }}</span>
            </el-form-item>
            <el-form-item v-if="previewData.metadata?.date" label="发布时间">
              <span>{{ previewData.metadata.date }}</span>
            </el-form-item>
            <el-form-item label="互动数据" v-if="previewData.metadata?.votes || previewData.metadata?.comments">
              <el-tag v-if="previewData.metadata?.votes" size="small" style="margin-right: 8px;">赞同 {{ previewData.metadata.votes }}</el-tag>
              <el-tag v-if="previewData.metadata?.comments" size="small" type="info">评论 {{ previewData.metadata.comments }}</el-tag>
            </el-form-item>
            <el-form-item v-if="previewData.metadata?.tags?.length" label="标签">
              <el-tag v-for="tag in previewData.metadata.tags" :key="tag" size="small" style="margin-right: 4px;">{{ tag }}</el-tag>
            </el-form-item>
          </template>
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

    <!-- 诊断结果弹窗 -->
    <el-dialog v-model="showDiag" title="页面 DOM 诊断" width="800px">
      <pre style="max-height: 60vh; overflow: auto; font-size: 12px; white-space: pre-wrap; word-break: break-all;">{{ diagResult }}</pre>
      <template #footer>
        <el-button @click="showDiag = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 书签管理弹窗 -->
    <el-dialog v-model="showBookmarkMgr" :title="editingBookmark ? '编辑书签' : '添加书签'" width="480px">
      <el-form label-width="60px" label-position="left">
        <el-form-item label="名称">
          <el-input v-model="bookmarkForm.name" placeholder="知乎" />
        </el-form-item>
        <el-form-item label="网址">
          <el-input v-model="bookmarkForm.url" placeholder="https://www.zhihu.com" />
        </el-form-item>
      </el-form>
      <el-divider />
      <div style="margin-bottom: 8px; font-weight: 500;">已有书签</div>
      <div v-for="bm in bookmarks" :key="bm.url" style="display: flex; align-items: center; justify-content: space-between; padding: 4px 0;">
        <span style="font-size: 13px;">{{ bm.name }}</span>
        <div>
          <el-button text size="small" @click="editBookmark(bm)">编辑</el-button>
          <el-button text type="danger" size="small" @click="removeBookmark(bm.url)">删除</el-button>
        </div>
      </div>
      <template #footer>
        <el-button @click="showBookmarkMgr = false">取消</el-button>
        <el-button type="primary" @click="saveBookmarkItem">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useCollectorStore } from '../stores/collector'
import { extract } from '../extractors'

const store = useCollectorStore()
const webviewEl = ref<any>(null)

const addressInput = ref('https://www.zhihu.com')
const currentUrl = ref('https://www.zhihu.com')
const isLoading = ref(false)
const isSaving = ref(false)
let loadingTimer: ReturnType<typeof setTimeout> | null = null
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

const isDev = import.meta.env.DEV
const isDiagnosing = ref(false)
const showDiag = ref(false)
const diagResult = ref('')

// ── 书签管理 ──
interface Bookmark { name: string; url: string }

const defaultBookmarks: Bookmark[] = [
  { name: '知乎', url: 'https://www.zhihu.com' },
  { name: '小红书', url: 'https://www.xiaohongshu.com' },
  { name: '微信公众号', url: 'https://mp.weixin.qq.com' },
  { name: '少数派', url: 'https://sspai.com' },
  { name: 'GitHub', url: 'https://github.com' },
]

const bookmarks = ref<Bookmark[]>([...defaultBookmarks])
const showBookmarkMgr = ref(false)
const editingBookmark = ref<Bookmark | null>(null)
const bookmarkForm = ref({ name: '', url: '' })
// 防止初始加载完成前的写操作覆盖已持久化的书签
let bookmarksReady = false

async function loadBookmarks() {
  try {
    const settings = await (window as any).collector?.getSettings()
    if (settings?.bookmarks?.length) {
      bookmarks.value = settings.bookmarks
    }
  } catch {}
  bookmarksReady = true
}

async function saveBookmarks() {
  // 只有在初始加载完成后才允许持久化，避免用默认书签覆盖已存数据
  if (!bookmarksReady) return
  try {
    await (window as any).collector?.setSettings({ bookmarks: bookmarks.value })
  } catch {}
}

function addBookmark() {
  const url = webviewEl.value?.getURL?.() || addressInput.value
  // new URL() 在 url 为空或非法时抛 TypeError，用 try-catch 兜底
  let name = ''
  try {
    name = webviewEl.value?.getTitle?.() || new URL(url).hostname
  } catch {
    name = url || '未知页面'
  }
  bookmarkForm.value = { name, url }
  editingBookmark.value = null
  showBookmarkMgr.value = true
}

function editBookmark(bm: Bookmark) {
  bookmarkForm.value = { ...bm }
  editingBookmark.value = bm
  showBookmarkMgr.value = true
}

function saveBookmarkItem() {
  if (!bookmarkForm.value.name || !bookmarkForm.value.url) return
  if (editingBookmark.value) {
    // 编辑
    const idx = bookmarks.value.findIndex(b => b.url === editingBookmark.value!.url)
    if (idx >= 0) bookmarks.value[idx] = { ...bookmarkForm.value }
  } else {
    // 新增（去重）
    if (!bookmarks.value.find(b => b.url === bookmarkForm.value.url)) {
      bookmarks.value.push({ ...bookmarkForm.value })
    }
  }
  showBookmarkMgr.value = false
  saveBookmarks()
}

function removeBookmark(url: string) {
  bookmarks.value = bookmarks.value.filter(b => b.url !== url)
  saveBookmarks()
}

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

function onStartLoading() {
  isLoading.value = true
  // 兜底：5秒后自动清除 loading，防止 SPA 导航卡住
  if (loadingTimer) clearTimeout(loadingTimer)
  loadingTimer = setTimeout(() => { isLoading.value = false }, 5000)
}

function onStopLoading() {
  isLoading.value = false
  if (loadingTimer) { clearTimeout(loadingTimer); loadingTimer = null }
  if (webviewEl.value) {
    addressInput.value = webviewEl.value.getURL?.() || addressInput.value
    canGoBack.value = webviewEl.value.canGoBack?.() ?? false
    canGoForward.value = webviewEl.value.canGoForward?.() ?? false
  }
}

function onNavigate(event: any) {
  // 仅同步地址栏；loading 状态由 did-stop-loading / did-finish-load 控制
  // 不在此处清除 isLoading，did-navigate 在页面内容加载完成前即触发
  if (event.url) addressInput.value = event.url
}

function onTitleUpdated(_event: any) {
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
    const url = webviewEl.value.getURL()
    const result = await extract(webviewEl.value, url)
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

async function diagnosePage() {
  if (!webviewEl.value) {
    ElMessage.warning('webview 未就绪')
    return
  }
  isDiagnosing.value = true
  try {
    const info = await webviewEl.value.executeJavaScript(
      '(function() {' +
      'var r = {};' +
      'r.url = location.href;' +
      'r.title = document.title;' +
      'r.isArticle = location.pathname.indexOf("/p/") === 0;' +
      'r.isAnswer = location.pathname.indexOf("/answer") >= 0;' +
      'r.isQuestion = location.pathname.indexOf("/question/") >= 0;' +

      'var modals = document.querySelectorAll("[class*=Modal]");' +
      'r.modalCount = modals.length;' +

      'r.titleCandidates = {' +
      '  h1: (document.querySelector("h1") || {}).textContent,' +
      '  PostTitle: (document.querySelector(".Post-Title") || {}).textContent,' +
      '  QuestionTitle: (document.querySelector(".QuestionHeader-title") || {}).textContent' +
      '};' +

      'r.authorCandidates = {' +
      '  AuthorInfoName: (document.querySelector(".AuthorInfo-name") || {}).textContent,' +
      '  UserLink: (document.querySelector(".UserLink-link") || {}).textContent' +
      '};' +

      'r.dateCandidates = {' +
      '  ContentItemTime: (document.querySelector(".ContentItem-time") || {}).textContent,' +
      '  time: (document.querySelector("time") || {}).textContent,' +
      '  dateAttr: (document.querySelector("time") || {}).getAttribute && document.querySelector("time").getAttribute("datetime")' +
      '};' +

      'var postContent = document.querySelector(".Post-RichTextContainer");' +
      'var richTexts = document.querySelectorAll(".RichText.ztext");' +
      'r.contentCandidates = {' +
      '  PostRichText: { found: !!postContent, len: postContent ? postContent.textContent.length : 0, htmlLen: postContent ? postContent.innerHTML.length : 0 },' +
      '  RichTextZtext: { count: richTexts.length, totalLen: Array.from(richTexts).reduce(function(s,e){ return s + e.textContent.length }, 0) }' +
      '};' +

      'r.interactionCandidates = {' +
      '  VoteButton: (document.querySelector(".VoteButton--up") || {}).textContent,' +
      '  CommentCount: (document.querySelector("[class*=CommentCount]") || {}).textContent' +
      '};' +

      'var imgs = document.querySelectorAll(".Post-RichTextContainer img, .RichText img");' +
      'r.imageCount = imgs.length;' +
      'r.imageSamples = Array.from(imgs).slice(0,5).map(function(i){ return { src: i.src, alt: i.alt } });' +

      'var seen = {};' +
      'r.matchedClasses = [];' +
      'document.querySelectorAll("*").forEach(function(el) {' +
      '  var cls = el.className;' +
      '  if (typeof cls === "string" && cls.length > 0 && cls.length < 100) {' +
      '    var keywords = ["Title","Author","content","Vote","Comment","Date","Time","Like","RichText"];' +
      '    for (var k = 0; k < keywords.length; k++) {' +
      '      if (cls.indexOf(keywords[k]) >= 0 && !seen[cls]) {' +
      '        seen[cls] = true;' +
      '        r.matchedClasses.push({ c: cls, t: el.tagName, s: el.textContent.substring(0,60) });' +
      '        break;' +
      '      }' +
      '    }' +
      '  }' +
      '});' +

      'return r;' +
      '})()'
    )
    diagResult.value = JSON.stringify(info, null, 2)
    showDiag.value = true
  } catch (e: any) {
    ElMessage.error('诊断失败：' + e.message)
  } finally {
    isDiagnosing.value = false
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

// 主进程通过 setWindowOpenHandler 拦截 target="_blank" 后，
// 发送此 IPC 通知渲染层同步地址栏
function onWebviewNavigated(_: unknown, url: string) {
  addressInput.value = url
}

onMounted(() => {
  if (webviewEl.value) {
    webviewEl.value.addEventListener?.('dom-ready', () => {
      canGoBack.value = webviewEl.value?.canGoBack() ?? false
      canGoForward.value = webviewEl.value?.canGoForward() ?? false
    })
  }
  // 监听主进程的导航通知（new-window 被拦截并在 webview 内导航后触发）
  window.electron?.ipcRenderer.on('webview:navigated', onWebviewNavigated)
  // 加载书签
  loadBookmarks()
})

onUnmounted(() => {
  window.electron?.ipcRenderer.removeListener('webview:navigated', onWebviewNavigated)
  // 组件销毁时清除保底计时器，防止回调触发在已卸载的组件上
  if (loadingTimer) { clearTimeout(loadingTimer); loadingTimer = null }
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
