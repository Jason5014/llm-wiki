/**
 * Electron 主进程入口
 * 负责：窗口创建、菜单、IPC 分发、应用生命周期
 */
import { app, BrowserWindow, shell, session, Menu } from 'electron'
import { join } from 'path'
import { electronApp, optimizer, is } from '@electron-toolkit/utils'
import Store from 'electron-store'
import { setupIpcHandlers } from './ipc'

// 持久化配置存储
export const store = new Store({
  defaults: {
    apiBaseUrl: 'http://localhost:8765',
    currentKbId: '',
    windowBounds: { width: 1400, height: 900 },
    bookmarks: [
      { name: '知乎', url: 'https://www.zhihu.com' },
      { name: '小红书', url: 'https://www.xiaohongshu.com' },
      { name: '微信公众号', url: 'https://mp.weixin.qq.com' },
      { name: '少数派', url: 'https://sspai.com' },
      { name: 'GitHub', url: 'https://github.com' },
    ],
  },
})

let mainWindow: BrowserWindow | null = null

function createWindow(): BrowserWindow {
  const bounds = store.get('windowBounds') as { width: number; height: number }

  mainWindow = new BrowserWindow({
    width: bounds.width,
    height: bounds.height,
    minWidth: 1000,
    minHeight: 700,
    show: false,
    autoHideMenuBar: false,
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    webPreferences: {
      preload: join(__dirname, '../preload/index.js'),
      sandbox: false,
      // 允许 webview 标签（用于内嵌浏览器）
      webviewTag: true,
      nodeIntegration: false,
      contextIsolation: true,
    },
  })

  mainWindow.on('ready-to-show', () => {
    mainWindow!.show()
  })

  // 记住窗口大小
  mainWindow.on('resize', () => {
    if (mainWindow && !mainWindow.isMaximized()) {
      const [width, height] = mainWindow.getSize()
      store.set('windowBounds', { width, height })
    }
  })

  // 外部链接在系统浏览器打开
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })

  // 加载渲染进程
  if (is.dev && process.env['ELECTRON_RENDERER_URL']) {
    mainWindow.loadURL(process.env['ELECTRON_RENDERER_URL'])
    mainWindow.webContents.openDevTools({ mode: 'detach' })
  } else {
    mainWindow.loadFile(join(__dirname, '../renderer/index.html'))
  }

  return mainWindow
}

function createMenu(): void {
  const template: Electron.MenuItemConstructorOptions[] = [
    {
      label: 'LLM Wiki Collector',
      submenu: [
        { role: 'about', label: '关于' },
        { type: 'separator' },
        { role: 'quit', label: '退出' },
      ],
    },
    {
      label: '编辑',
      submenu: [
        { role: 'undo', label: '撤销' },
        { role: 'redo', label: '重做' },
        { type: 'separator' },
        { role: 'cut', label: '剪切' },
        { role: 'copy', label: '复制' },
        { role: 'paste', label: '粘贴' },
        { role: 'selectAll', label: '全选' },
      ],
    },
    {
      label: '视图',
      submenu: [
        { role: 'reload', label: '重新加载' },
        { role: 'toggleDevTools', label: '开发者工具' },
        { type: 'separator' },
        { role: 'resetZoom', label: '重置缩放' },
        { role: 'zoomIn', label: '放大' },
        { role: 'zoomOut', label: '缩小' },
        { type: 'separator' },
        { role: 'togglefullscreen', label: '全屏' },
      ],
    },
  ]

  Menu.setApplicationMenu(Menu.buildFromTemplate(template))
}

// ─────────────────────────────────────────────
// 应用生命周期
// ─────────────────────────────────────────────

app.whenReady().then(() => {
  electronApp.setAppUserModelId('com.llmwiki.collector')

  // 快捷键优化（开发模式下 F12 打开 DevTools）
  app.on('browser-window-created', (_, window) => {
    optimizer.watchWindowShortcuts(window)
  })

  // 设置内嵌浏览器的持久化 Session
  _setupCollectorSession()

  createMenu()
  createWindow()
  setupIpcHandlers(store as any)

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow()
    }
  })
})

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit()
  }
})

/**
 * 拦截 webview 内所有新窗口请求（target="_blank"、window.open）
 * Electron 28+ 废弃了 webview 的 new-window DOM 事件，
 * 必须在主进程通过 web-contents-created 拦截 webview 的 webContents。
 *
 * 策略：让 webview 在原窗口内导航到目标 URL，通知渲染进程同步地址栏。
 */
app.on('web-contents-created', (_, contents) => {
  if (contents.getType() !== 'webview') return

  contents.setWindowOpenHandler(({ url }) => {
    // 在 webview 内部导航，不开新窗口
    contents.loadURL(url)
    // 通知渲染进程同步地址栏显示
    mainWindow?.webContents.send('webview:navigated', url)
    return { action: 'deny' }
  })
})

/**
 * 配置内嵌浏览器的持久化 Session
 * partition: 'persist:wiki-collector' 会将 Cookie 保存到磁盘
 * 应用重启后保持登录状态
 */
function _setupCollectorSession(): void {
  const collectorSession = session.fromPartition('persist:wiki-collector')

  // 允许所有内容（采集用途，不需要严格 CSP）
  collectorSession.webRequest.onHeadersReceived((details, callback) => {
    callback({
      responseHeaders: {
        ...details.responseHeaders,
        // 移除可能阻止内嵌的 X-Frame-Options
        'X-Frame-Options': [],
        'x-frame-options': [],
      },
    })
  })
}

export { mainWindow }
