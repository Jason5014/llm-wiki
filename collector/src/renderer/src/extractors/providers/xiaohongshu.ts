/**
 * 小红书内容提取器
 *
 * 支持：图文笔记、视频笔记
 * 提取：标题 / 正文 / 图片 alt 描述 / 话题标签 / 互动数据
 */
import type { ExtractResult } from '../index'
import { HTML_TO_MARKDOWN_FN } from '../htmlToMarkdown'

export async function extractXiaohongshu(
  webview: any,
  url: string
): Promise<ExtractResult> {
  const result = await webview.executeJavaScript(`
    (function() {
      ${HTML_TO_MARKDOWN_FN}

      // 标题
      var title =
        (document.querySelector('#detail-title') || {}).textContent ||
        (document.querySelector('.title') || {}).textContent ||
        document.title;
      title = (title || '').trim();

      // 正文（优先取富文本容器，降级取纯文字）
      var descEl =
        document.querySelector('#detail-desc') ||
        document.querySelector('.desc') ||
        document.querySelector('.note-content');
      var content = descEl ? htmlToMd(descEl) : '';

      // 话题标签
      var tags = Array.from(document.querySelectorAll('a[href*="/search_result/?keyword="]'))
        .map(function(a) {
          var t = (a.textContent || '').trim().replace(/^#/, '');
          return t;
        })
        .filter(function(t) { return t.length > 0 && t.length < 20; });

      // 图片 alt 描述（图文笔记轮播图）
      var imgAlts = Array.from(
        document.querySelectorAll('.swiper-slide img, .media-container img')
      )
        .map(function(img) { return (img.getAttribute('alt') || '').trim(); })
        .filter(Boolean);

      if (imgAlts.length) {
        content += '\\n\\n**图片描述：**\\n' + imgAlts.map(function(a) { return '- ' + a; }).join('\\n');
      }

      // 互动数据
      var likes    = (document.querySelector('.like-wrapper .count') || {}).textContent || '0';
      var collects = (document.querySelector('.collect-wrapper .count') || {}).textContent || '0';
      var comments = (document.querySelector('.chat-wrapper .count') || {}).textContent || '0';

      // 作者
      var author = (document.querySelector('.author-wrapper .username') || {}).textContent ||
                   (document.querySelector('.user-name') || {}).textContent || '';

      return {
        title: title,
        content: content.trim(),
        metadata: {
          source:   'xiaohongshu',
          author:   author.trim() || undefined,
          likes:    likes.trim(),
          collects: collects.trim(),
          comments: comments.trim(),
          tags:     tags.length ? tags : undefined,
        }
      };
    })()
  `)

  return {
    title: result.title || url,
    content: result.content || '',
    url,
    metadata: result.metadata || { source: 'xiaohongshu' },
  }
}
