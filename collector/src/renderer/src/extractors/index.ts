/**
 * 内容提取器注册表
 *
 * 用法：
 *   const result = await extract(webviewElement, url)
 *
 * 新增网站：在 PROVIDERS 数组中添加一项即可，不需要改 BrowserView.vue。
 */
import { extractZhihu } from './providers/zhihu'
import { extractXiaohongshu } from './providers/xiaohongshu'
import { extractGeneric } from './providers/generic'

// ─────────────────────────────────────────────
// 公共类型
// ─────────────────────────────────────────────

export interface ExtractMetadata {
  source: string
  pageType?: string
  via?: string
  author?: string
  authorBio?: string
  date?: string
  votes?: string
  comments?: string
  tags?: string[]
  followCount?: string
  answerCount?: number
  likes?: string
  collects?: string
  hostname?: string
  [key: string]: unknown
}

export interface ExtractResult {
  title: string
  content: string
  url: string
  metadata: ExtractMetadata
}

// ─────────────────────────────────────────────
// Provider 接口
// ─────────────────────────────────────────────

interface ContentProvider {
  /** 用于日志 / 调试的可读名称 */
  name: string
  /** 根据域名判断是否由此 Provider 处理 */
  matches(hostname: string): boolean
  /** 执行提取，返回结构化结果 */
  extract(webview: any, url: string): Promise<ExtractResult>
}

// ─────────────────────────────────────────────
// 注册表（按匹配优先级排列，先匹配先使用）
// ─────────────────────────────────────────────

const PROVIDERS: ContentProvider[] = [
  {
    name: 'zhihu',
    matches: (h) => h.includes('zhihu.com'),
    extract: extractZhihu,
  },
  {
    name: 'xiaohongshu',
    matches: (h) => h.includes('xiaohongshu.com'),
    extract: extractXiaohongshu,
  },
  // ─── 在此处添加新 Provider ─────────────────
  // {
  //   name: 'sspai',
  //   matches: (h) => h.includes('sspai.com'),
  //   extract: extractSspai,
  // },
  // {
  //   name: 'weixin',
  //   matches: (h) => h.includes('mp.weixin.qq.com'),
  //   extract: extractWeixin,
  // },
]

// 兜底（通用提取器，始终匹配）
const GENERIC_PROVIDER: ContentProvider = {
  name: 'generic',
  matches: () => true,
  extract: extractGeneric,
}

// ─────────────────────────────────────────────
// 对外入口
// ─────────────────────────────────────────────

/**
 * 根据当前页面 URL 自动选择最合适的 Provider 并提取内容
 */
export async function extract(webview: any, url: string): Promise<ExtractResult> {
  let hostname = ''
  try {
    hostname = new URL(url).hostname
  } catch {
    // url 非法时使用通用提取器
  }

  const provider = PROVIDERS.find((p) => p.matches(hostname)) ?? GENERIC_PROVIDER
  return provider.extract(webview, url)
}
