/**
 * 通用内容提取器（兜底）
 *
 * 思路来自 Mozilla Readability：
 *   1. 找到页面主内容区（article / main / [role=main] 等语义元素）
 *   2. 移除噪音（导航 / 广告 / 侧栏 / 脚注）
 *   3. 转换为带结构的 Markdown
 *
 * 不依赖任何外部库，完全在注入脚本中运行。
 */
import type { ExtractResult } from '../index'
import { HTML_TO_MARKDOWN_FN } from '../htmlToMarkdown'

export async function extractGeneric(
  webview: any,
  url: string
): Promise<ExtractResult> {
  const result = await webview.executeJavaScript(`
    (function() {
      ${HTML_TO_MARKDOWN_FN}

      // ── 1. 复制 DOM，移除噪音 ─────────────────────────────
      var docClone = document.cloneNode(true);
      var noiseSelectors = [
        'script', 'style', 'noscript', 'iframe',
        'nav', 'header', 'footer', 'aside',
        '[role="navigation"]', '[role="banner"]', '[role="contentinfo"]', '[role="complementary"]',
        '.ad', '#ad', '.ads', '.advertisement', '.sponsor',
        '.sidebar', '.side-bar', '#sidebar',
        '.comment', '.comments', '#comments',
        '.related', '.recommend',
        '.share', '.social',
        'form',
      ];
      noiseSelectors.forEach(function(sel) {
        try {
          docClone.querySelectorAll(sel).forEach(function(el) { el.remove(); });
        } catch(e) {}
      });

      // ── 2. 按优先级寻找主内容区 ──────────────────────────
      var contentSelectors = [
        'article',
        '[role="main"]',
        'main',
        '.post-content', '.article-content', '.entry-content',
        '.content-body', '.article-body',
        '#content', '#main-content', '#post-content',
        '.post', '.article',
        '.container article',
      ];
      var contentEl = null;
      for (var i = 0; i < contentSelectors.length; i++) {
        var candidate = docClone.querySelector(contentSelectors[i]);
        // 内容区至少应有 200 个字符
        if (candidate && (candidate.textContent || '').trim().length > 200) {
          contentEl = candidate;
          break;
        }
      }
      if (!contentEl) contentEl = docClone.body;

      // ── 3. 提取元数据 ─────────────────────────────────────
      var title = document.title;
      // OGP / 标准 meta
      var ogTitle = (document.querySelector('meta[property="og:title"]') || {}).getAttribute &&
                     document.querySelector('meta[property="og:title"]').getAttribute('content');
      if (ogTitle) title = ogTitle;

      var author =
        (document.querySelector('meta[name="author"]') || {}).getAttribute &&
        document.querySelector('meta[name="author"]').getAttribute('content') || '';
      if (!author) {
        author = (document.querySelector('.author, .byline, [rel="author"]') || {}).textContent || '';
      }

      // 发布时间
      var dateEl = document.querySelector('time[datetime], time[pubdate], .publish-date, .date, .post-date, .entry-date');
      var date = '';
      if (dateEl) {
        date = dateEl.getAttribute('datetime') || dateEl.textContent || '';
      }
      if (!date) {
        var dateMeta = document.querySelector('meta[property="article:published_time"]');
        if (dateMeta) date = dateMeta.getAttribute('content') || '';
      }

      // 关键词 / 标签
      var keywordsMeta = document.querySelector('meta[name="keywords"]');
      var tags = keywordsMeta
        ? (keywordsMeta.getAttribute('content') || '').split(',').map(function(k) { return k.trim(); }).filter(Boolean)
        : [];

      // ── 4. 转 Markdown ────────────────────────────────────
      var content = htmlToMd(contentEl);
      // 控制最大长度
      if (content.length > 12000) {
        content = content.substring(0, 12000) + '\\n\\n…（内容已截断）';
      }

      return {
        title: title.trim(),
        content: content,
        metadata: {
          source:   'web',
          hostname: location.hostname,
          author:   author.trim() || undefined,
          date:     date.trim()   || undefined,
          tags:     tags.length ? tags : undefined,
        }
      };
    })()
  `)

  return {
    title: result.title || url,
    content: result.content || '',
    url,
    metadata: result.metadata || { source: 'web' },
  }
}
