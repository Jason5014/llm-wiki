/**
 * IPC 通信处理器
 * 渲染进程通过 preload 暴露的 API 调用这里的处理函数
 */
import { ipcMain, session, BrowserWindow, dialog } from 'electron'
import axios from 'axios'
import * as fs from 'fs'
import * as path from 'path'
import type Store from 'electron-store'

// ─────────────────────────────────────────────
// 类型定义
// ─────────────────────────────────────────────

interface ExtractResult {
  title: string
  content: string
  url: string
  metadata: Record<string, unknown>
}

// ─────────────────────────────────────────────
// 工具：将 axios 错误转成可跨 IPC 传递的普通 Error
// axios 错误对象含循环引用（config/request/response），
// 直接抛出会触发 Electron DataCloneError "An object could not be cloned"
// ─────────────────────────────────────────────

function ipcError(e: unknown): Error {
  if (axios.isAxiosError(e)) {
    const detail = e.response?.data?.detail
    if (typeof detail === 'string') return new Error(detail)
    if (Array.isArray(detail)) return new Error(detail.map((d: any) => d.msg).join('; '))
    if (e.response) return new Error(`HTTP ${e.response.status}: ${e.response.statusText}`)
    if (e.request) return new Error('后端无响应，请确认服务已启动')
  }
  if (e instanceof Error) return new Error(e.message)
  return new Error(String(e))
}

// ─────────────────────────────────────────────
// 注册所有 IPC 处理器
// ─────────────────────────────────────────────

export function setupIpcHandlers(store: InstanceType<typeof Store<Record<string, unknown>>>): void {

  // ── 设置 ──────────────────────────────────

  ipcMain.handle('settings:get', () => {
    return {
      apiBaseUrl: store.get('apiBaseUrl'),
      currentKbId: store.get('currentKbId'),
      bookmarks: store.get('bookmarks'),
    }
  })

  ipcMain.handle('settings:set', (_, settings: Record<string, unknown>) => {
    for (const [key, value] of Object.entries(settings)) {
      store.set(key, value)
    }
    return true
  })

  // ── 知识库 API ────────────────────────────

  ipcMain.handle('api:listKbs', async () => {
    try {
      const baseUrl = store.get('apiBaseUrl') as string
      const resp = await axios.get(`${baseUrl}/api/kb/`)
      return resp.data
    } catch (e) { throw ipcError(e) }
  })

  ipcMain.handle('api:createKb', async (_, { name, domain, description }: {
    name: string; domain?: string[]; description?: string
  }) => {
    try {
      const baseUrl = store.get('apiBaseUrl') as string
      const resp = await axios.post(`${baseUrl}/api/kb/`, { name, domain, description })
      return resp.data
    } catch (e) { throw ipcError(e) }
  })

  ipcMain.handle('api:submitDoc', async (_, { kbId, doc }: { kbId: string; doc: ExtractResult }) => {
    try {
      const baseUrl = store.get('apiBaseUrl') as string
      const resp = await axios.post(`${baseUrl}/api/collect/${kbId}/raw`, doc)
      return resp.data
    } catch (e) { throw ipcError(e) }
  })

  ipcMain.handle('api:batchSubmit', async (_, { kbId, docs }: { kbId: string; docs: ExtractResult[] }) => {
    try {
      const baseUrl = store.get('apiBaseUrl') as string
      const resp = await axios.post(`${baseUrl}/api/collect/${kbId}/batch`, { documents: docs })
      return resp.data
    } catch (e) { throw ipcError(e) }
  })

  ipcMain.handle('api:uploadFile', async (_, { kbId, filePath }: { kbId: string; filePath: string }) => {
    try {
      const baseUrl = store.get('apiBaseUrl') as string
      const FormData = (await import('form-data')).default
      const form = new FormData()
      form.append('file', fs.createReadStream(filePath), path.basename(filePath))
      const resp = await axios.post(`${baseUrl}/api/collect/${kbId}/upload`, form, {
        headers: form.getHeaders(),
      })
      return resp.data
    } catch (e) { throw ipcError(e) }
  })

  // ── 内嵌浏览器内容提取 ───────────────────

  ipcMain.handle('browser:extractContent', async (_, { webContentsId }: { webContentsId: number }) => {
    const wc = BrowserWindow.getAllWindows()
      .flatMap(w => w.getBrowserViews ? w.getBrowserViews() : [])
      .find(bv => bv.webContents.id === webContentsId)
      ?.webContents
      ?? BrowserWindow.getAllWindows().find(w => w.webContents.id === webContentsId)?.webContents

    if (!wc) {
      throw new Error('WebContents not found')
    }

    return await extractContentFromWebContents(wc)
  })

  // ── 文件选择对话框 ────────────────────────

  ipcMain.handle('dialog:openFiles', async () => {
    const result = await dialog.showOpenDialog({
      properties: ['openFile', 'multiSelections'],
      filters: [
        { name: '支持的文件', extensions: ['md', 'txt', 'pdf', 'html'] },
        { name: '所有文件', extensions: ['*'] },
      ],
    })
    return result.filePaths
  })

  // ── Cookie 管理 ───────────────────────────

  ipcMain.handle('cookies:getAll', async (_, domain?: string) => {
    const collectorSession = session.fromPartition('persist:wiki-collector')
    return await collectorSession.cookies.get(domain ? { domain } : {})
  })

  ipcMain.handle('cookies:clear', async (_, domain?: string) => {
    const collectorSession = session.fromPartition('persist:wiki-collector')
    if (domain) {
      const cookies = await collectorSession.cookies.get({ domain })
      for (const cookie of cookies) {
        await collectorSession.cookies.remove(`https://${domain}`, cookie.name)
      }
    }
    return true
  })
}

// ─────────────────────────────────────────────
// 内容提取（Content Providers）
// ─────────────────────────────────────────────

/**
 * 从 WebContents 提取页面内容
 * 根据 URL 自动选择对应的 Provider
 */
async function extractContentFromWebContents(
  wc: Electron.WebContents
): Promise<ExtractResult> {
  const url = wc.getURL()
  const hostname = new URL(url).hostname

  if (hostname.includes('xiaohongshu.com')) {
    return await extractXiaohongshu(wc, url)
  } else if (hostname.includes('zhihu.com')) {
    return await extractZhihu(wc, url)
  } else {
    return await extractDefault(wc, url)
  }
}

/**
 * 小红书内容提取
 */
async function extractXiaohongshu(
  wc: Electron.WebContents,
  url: string
): Promise<ExtractResult> {
  const result = await wc.executeJavaScript(`
    (function() {
      // 提取标题
      const title = document.querySelector('#detail-title')?.textContent?.trim()
        || document.querySelector('.title')?.textContent?.trim()
        || document.title;

      // 提取正文
      const contentEl = document.querySelector('#detail-desc')
        || document.querySelector('.desc')
        || document.querySelector('.note-content');
      const content = contentEl?.textContent?.trim() || '';

      // 提取互动数据
      const likes = document.querySelector('.like-wrapper .count')?.textContent?.trim() || '0';
      const collects = document.querySelector('.collect-wrapper .count')?.textContent?.trim() || '0';
      const comments = document.querySelector('.chat-wrapper .count')?.textContent?.trim() || '0';

      // 提取图片描述
      const images = Array.from(document.querySelectorAll('.swiper-slide img'))
        .map((img) => img.getAttribute('alt') || '')
        .filter(Boolean)
        .join('\\n');

      return {
        title,
        content: content + (images ? '\\n\\n图片描述：\\n' + images : ''),
        metadata: { likes, collects, comments, source: 'xiaohongshu' }
      };
    })()
  `)

  return {
    title: result.title || url,
    content: result.content || '',
    url,
    metadata: result.metadata,
  }
}

/**
 * 知乎内容提取
 */
async function extractZhihu(
  wc: Electron.WebContents,
  url: string
): Promise<ExtractResult> {
  const result = await wc.executeJavaScript(`
    (function() {
      // 问题/回答/文章
      const isArticle = window.location.pathname.startsWith('/p/');
      const isAnswer = window.location.pathname.includes('/answers/') || window.location.pathname.includes('/answer/');

      let title = '';
      let content = '';

      if (isArticle) {
        title = document.querySelector('.Post-Title')?.textContent?.trim() || document.title;
        content = document.querySelector('.Post-RichTextContainer')?.textContent?.trim() || '';
      } else {
        // 问题 + 回答
        title = document.querySelector('.QuestionHeader-title')?.textContent?.trim() || document.title;
        const answers = Array.from(document.querySelectorAll('.RichText.ztext'))
          .map((el) => el.textContent?.trim())
          .filter(Boolean)
          .join('\\n\\n---\\n\\n');
        content = answers || document.body.innerText?.substring(0, 5000) || '';
      }

      const voteCount = document.querySelector('.VoteButton--up .Button-label')?.textContent?.trim() || '0';

      return {
        title,
        content,
        metadata: { votes: voteCount, source: 'zhihu' }
      };
    })()
  `)

  return {
    title: result.title || url,
    content: result.content || '',
    url,
    metadata: result.metadata,
  }
}

/**
 * 通用内容提取（基于 Readability）
 */
async function extractDefault(
  wc: Electron.WebContents,
  url: string
): Promise<ExtractResult> {
  // 注入 Readability.js 并提取正文
  const result = await wc.executeJavaScript(`
    (function() {
      // 简单的文本提取（不依赖外部库）
      // 移除 nav, footer, aside, script, style 等噪音元素
      const clone = document.cloneNode(true);

      // 移除不需要的元素
      ['script', 'style', 'nav', 'footer', 'aside', 'header', '.ad', '#ad', '.advertisement'].forEach(sel => {
        try {
          clone.querySelectorAll(sel).forEach(el => el.remove());
        } catch(e) {}
      });

      // 尝试找到主要内容区
      const mainEl = clone.querySelector('main, article, [role="main"], .post-content, .article-content, .content')
        || clone.querySelector('.container, #content, #main');

      const contentEl = mainEl || clone.body;
      const text = contentEl ? contentEl.innerText || contentEl.textContent : '';

      // 清理多余空行
      const cleaned = text?.replace(/\\n{3,}/g, '\\n\\n').trim() || '';

      return {
        title: document.title,
        content: cleaned.substring(0, 10000),
        metadata: { source: 'web', hostname: window.location.hostname }
      };
    })()
  `)

  return {
    title: result.title || url,
    content: result.content || '',
    url,
    metadata: result.metadata,
  }
}
