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

      // 关键词 / 标签（多来源合并）
      var tags = [];
      // 1. <meta name="keywords">
      var keywordsMeta = document.querySelector('meta[name="keywords"]');
      if (keywordsMeta) {
        (keywordsMeta.getAttribute('content') || '').split(',').forEach(function(k) {
          k = k.trim(); if (k && k.length < 30) tags.push(k);
        });
      }
      // 2. <meta property="article:tag">
      document.querySelectorAll('meta[property="article:tag"]').forEach(function(m) {
        var v = (m.getAttribute('content') || '').trim();
        if (v && v.length < 30 && tags.indexOf(v) === -1) tags.push(v);
      });
      // 3. <meta property="og:article:tag">
      document.querySelectorAll('meta[property="og:article:tag"]').forEach(function(m) {
        var v = (m.getAttribute('content') || '').trim();
        if (v && v.length < 30 && tags.indexOf(v) === -1) tags.push(v);
      });
      // 4. 页面上的标签元素
      var tagSelectors = '.tag, .tags a, .post-tag, .article-tag, .label, .category, [rel="tag"]';
      document.querySelectorAll(tagSelectors).forEach(function(el) {
        var t = (el.textContent || '').trim().replace(/^#/, '');
        if (t && t.length > 1 && t.length < 30 && tags.indexOf(t) === -1) tags.push(t);
      });
      // 5. 面包屑（最后一级作为分类）
      var breadcrumb = document.querySelector('.breadcrumb, [class*="breadcrumb"], nav[aria-label*="bread"]');
      if (breadcrumb) {
        var lastCrumb = breadcrumb.querySelector('li:last-child a, span:last-child');
        if (lastCrumb) {
          var cat = (lastCrumb.textContent || '').trim();
          if (cat && cat.length < 30 && tags.indexOf(cat) === -1) tags.push(cat);
        }
      }
      // 限制标签数量
      tags = tags.slice(0, 15);

      // ── 4. 转 Markdown ────────────────────────────────────
      // 统计有效图片数（用于 Tier0 质检）
      var allImgs = contentEl.querySelectorAll('img');
      var validImgCount = 0;
      allImgs.forEach(function(img) {
        var src = img.getAttribute('data-original') || img.getAttribute('data-actualsrc') || img.getAttribute('data-src') || img.src || '';
        // 跳过空 src、data: URI、1px 跟踪像素
        if (!src || src.startsWith('data:')) return;
        var w = img.naturalWidth || img.width || 0;
        var h = img.naturalHeight || img.height || 0;
        // naturalWidth/height 为 0 说明未加载，但仍算有效（有真实 URL）
        // 只排除明确的小图标（< 10px 且已加载）
        if (w > 0 && w < 10 && h > 0 && h < 10) return;
        validImgCount++;
      });

      var content = htmlToMd(contentEl);

      // 更多元数据
      var ogDesc = (document.querySelector('meta[property="og:description"]') || {});
      var description = (ogDesc.getAttribute && ogDesc.getAttribute('content')) ||
                        (document.querySelector('meta[name="description"]') || {}).getAttribute &&
                        document.querySelector('meta[name="description"]').getAttribute('content') || '';
      var siteName = (document.querySelector('meta[property="og:site_name"]') || {});
      var site = (siteName.getAttribute && siteName.getAttribute('content')) || location.hostname;
      var section = (document.querySelector('meta[property="article:section"]') || {});
      var category = (section.getAttribute && section.getAttribute('content')) || '';

      return {
        title: title.trim(),
        content: content,
        metadata: {
          source:      'web',
          hostname:    location.hostname,
          site_name:   site.trim() || undefined,
          author:      author.trim() || undefined,
          date:        date.trim()   || undefined,
          description: (description || '').trim().substring(0, 200) || undefined,
          category:    category.trim() || undefined,
          tags:        tags.length ? tags : undefined,
          img_count:   validImgCount,
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
