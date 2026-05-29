/**
 * 知乎内容提取器
 *
 * 支持三种场景：
 *   1. 文章页   /p/{id}          — 标题 / 正文 / 作者 / 发布时间 / 点赞 / 标签
 *   2. 问题页   /question/{id}   — 问题描述 + 前 N 条回答（含作者 / 点赞）
 *   3. 首页弹框 （URL 不变）      — 从 Modal DOM 提取文章/问答预览
 */
import type { ExtractResult } from '../index'
import { HTML_TO_MARKDOWN_FN } from '../htmlToMarkdown'

export async function extractZhihu(
  webview: any,
  url: string
): Promise<ExtractResult> {
  const result = await webview.executeJavaScript(`
    (function() {
      ${HTML_TO_MARKDOWN_FN}

      var path = location.pathname;

      // ──────────────────────────────────────────────────────
      // 场景 1：首页/列表页弹框（知乎点击卡片会弹出 Modal 预览）
      // ──────────────────────────────────────────────────────
      var modal = document.querySelector(
        '.Modal--default, .Modal-content, [class*="ContentModal"]'
      );
      if (modal) {
        var mTitle =
          (modal.querySelector('.Post-Title') || {}).textContent ||
          (modal.querySelector('.QuestionHeader-title') || {}).textContent ||
          (modal.querySelector('h1, h2') || {}).textContent ||
          document.title;
        mTitle = (mTitle || '').trim();

        var mContentEl =
          modal.querySelector('.Post-RichTextContainer') ||
          modal.querySelector('.RichText.ztext');
        var mContent = mContentEl
          ? htmlToMd(mContentEl)
          : (modal.innerText || '').replace(/\\n{3,}/g, '\\n\\n').trim().substring(0, 8000);

        // 找到弹框内文章的真实 URL
        var mLink =
          (modal.querySelector('a[href*="/p/"], a[href*="/question/"]') || {}).href ||
          (document.querySelector('link[rel="canonical"]') || {}).href ||
          location.href;

        var mAuthor = (modal.querySelector('.AuthorInfo-name') || {}).textContent || '';
        var mDate   = (modal.querySelector('.ContentItem-time') || {}).textContent || '';
        var mVotes  = (modal.querySelector('.VoteButton--up .Button-label') || {}).textContent || '';

        return {
          title: mTitle,
          content: mContent,
          canonicalUrl: mLink.trim(),
          metadata: {
            source: 'zhihu',
            via: 'modal',
            author: mAuthor.trim() || undefined,
            date:   mDate.trim()   || undefined,
            votes:  mVotes.trim()  || undefined,
          }
        };
      }

      // ──────────────────────────────────────────────────────
      // 场景 2：文章页 /p/{id}
      // ──────────────────────────────────────────────────────
      if (path.startsWith('/p/')) {
        var title = (document.querySelector('.Post-Title') || {}).textContent || document.title;
        var contentEl = document.querySelector('.Post-RichTextContainer');
        var content = contentEl ? htmlToMd(contentEl) : '';

        var author    = (document.querySelector('.AuthorInfo-name') || {}).textContent || '';
        var authorBio = (document.querySelector('.AuthorInfo-detail') || {}).textContent || '';
        var dateEl    = document.querySelector('.ContentItem-time');
        var date      = dateEl ? (dateEl.textContent || '') : '';
        var votes     = (document.querySelector('.VoteButton--up .Button-label') || {}).textContent || '';
        var comments  = (document.querySelector('[class*="CommentCount"]') || {}).textContent || '';
        var tags      = Array.from(document.querySelectorAll('.Tag-item, .ArticleTag-item'))
                          .map(function(t) { return (t.textContent || '').trim(); })
                          .filter(Boolean);

        return {
          title: title.trim(),
          content: content,
          canonicalUrl: null,
          metadata: {
            source:    'zhihu',
            pageType:  'article',
            author:    author.trim()    || undefined,
            authorBio: authorBio.trim() || undefined,
            date:      date.trim()      || undefined,
            votes:     votes.trim()     || undefined,
            comments:  comments.trim()  || undefined,
            tags:      tags.length ? tags : undefined,
          }
        };
      }

      // ──────────────────────────────────────────────────────
      // 场景 3：问题页 /question/{id}
      // ──────────────────────────────────────────────────────
      if (path.startsWith('/question/')) {
        var qTitle  = (document.querySelector('.QuestionHeader-title') || {}).textContent || document.title;
        var qDetail = (document.querySelector('.QuestionHeader-detail .RichText') || {}).textContent || '';
        var followCount = (document.querySelector('.NumberBoard-itemValue') || {}).textContent || '';

        // 提取页面上所有可见回答（最多 10 条）
        var answerItems = Array.from(
          document.querySelectorAll('.List-item[data-za-detail-view-id], .AnswerItem')
        ).slice(0, 10);

        var answers = answerItems.map(function(item) {
          var aAuthor = (item.querySelector('.AuthorInfo-name') || {}).textContent || '匿名用户';
          var aVotes  = (item.querySelector('.VoteButton--up .Button-label') || {}).textContent || '0';
          var aEl     = item.querySelector('.RichText.ztext');
          var aContent = aEl ? htmlToMd(aEl) : '';
          if (!aContent.trim()) return null;
          return '**' + aAuthor.trim() + '**（赞同 ' + aVotes.trim() + '）\\n\\n' + aContent;
        }).filter(Boolean);

        var content =
          (qDetail.trim() ? '## 问题描述\\n\\n' + qDetail.trim() + '\\n\\n' : '') +
          (answers.length ? '## 高赞回答\\n\\n' + answers.join('\\n\\n---\\n\\n') : '（暂无回答）');

        return {
          title: qTitle.trim(),
          content: content,
          canonicalUrl: null,
          metadata: {
            source:      'zhihu',
            pageType:    'question',
            followCount: followCount.trim() || undefined,
            answerCount: answers.length,
          }
        };
      }

      // ──────────────────────────────────────────────────────
      // 兜底：其他知乎页面
      // ──────────────────────────────────────────────────────
      var fallbackEl = document.querySelector('.RichText.ztext, article, main') || document.body;
      return {
        title: document.title,
        content: htmlToMd(fallbackEl).substring(0, 10000),
        canonicalUrl: null,
        metadata: { source: 'zhihu', pageType: 'other' }
      };
    })()
  `)

  return {
    title: result.title || url,
    content: result.content || '',
    url: result.canonicalUrl || url,
    metadata: result.metadata || { source: 'zhihu' },
  }
}
