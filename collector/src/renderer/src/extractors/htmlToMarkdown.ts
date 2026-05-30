/**
 * HTML → 轻量 Markdown 转换器
 *
 * 作为字符串注入目标页面的 executeJavaScript 上下文中运行，
 * 保留文章的层次结构（标题 / 列表 / 代码块 / 引用），
 * 让存入知识库的内容比纯 textContent 更有语义价值。
 *
 * 使用方法：在注入脚本顶部展开此字符串
 *   `${HTML_TO_MARKDOWN_FN}\n...你的提取逻辑...`
 */
export const HTML_TO_MARKDOWN_FN = `
function htmlToMd(el) {
  if (!el) return '';
  var buf = [];

  function walk(node) {
    if (!node) return;

    // 文本节点
    if (node.nodeType === 3) {
      buf.push(node.textContent);
      return;
    }

    if (node.nodeType !== 1) return;
    var tag = node.tagName.toLowerCase();

    // 忽略噪音
    if (tag === 'script' || tag === 'style' || tag === 'noscript' || tag === 'button') return;

    // 不可见元素
    var style = window.getComputedStyle ? window.getComputedStyle(node) : null;
    if (style && (style.display === 'none' || style.visibility === 'hidden')) return;

    switch (tag) {
      case 'h1': buf.push('\\n# ');   walkChildren(node); buf.push('\\n\\n'); break;
      case 'h2': buf.push('\\n## ');  walkChildren(node); buf.push('\\n\\n'); break;
      case 'h3': buf.push('\\n### '); walkChildren(node); buf.push('\\n\\n'); break;
      case 'h4': case 'h5': case 'h6':
        buf.push('\\n#### '); walkChildren(node); buf.push('\\n\\n'); break;

      case 'p':
        walkChildren(node);
        buf.push('\\n\\n');
        break;

      case 'br':
        buf.push('\\n');
        break;

      case 'ul': case 'ol':
        buf.push('\\n');
        walkChildren(node);
        buf.push('\\n');
        break;

      case 'li':
        buf.push('\\n- ');
        walkChildren(node);
        break;

      case 'strong': case 'b':
        buf.push('**'); walkChildren(node); buf.push('**');
        break;

      case 'em': case 'i':
        buf.push('_'); walkChildren(node); buf.push('_');
        break;

      case 'code':
        // 行内代码（父节点不是 pre）
        if (!node.closest || !node.closest('pre')) {
          buf.push('\`'); walkChildren(node); buf.push('\`');
        } else {
          walkChildren(node);
        }
        break;

      case 'pre':
        // 提取语言标识（class="language-python" 之类）
        var lang = '';
        var codeEl = node.querySelector('code');
        if (codeEl) {
          var m = (codeEl.className || '').match(/language-([\\w-]+)/);
          if (m) lang = m[1];
        }
        buf.push('\\n\`\`\`' + lang + '\\n');
        buf.push((codeEl || node).textContent || '');
        buf.push('\\n\`\`\`\\n\\n');
        break;

      case 'blockquote':
        buf.push('\\n> ');
        walkChildren(node);
        buf.push('\\n\\n');
        break;

      case 'hr':
        buf.push('\\n---\\n\\n');
        break;

      case 'a':
        // 只保留链接文字，不保留 href（知识库用途不需要）
        walkChildren(node);
        break;

      case 'img':
        (function() {
          var src = node.getAttribute('data-original')
            || node.getAttribute('data-actualsrc')
            || node.getAttribute('data-src')
            || node.src || '';
          if (!src || src.startsWith('data:')) return;
          var alt = (node.alt || node.getAttribute('aria-label') || '').trim();
          buf.push('![' + alt + '](' + src + ')');
        })();
        break;

      case 'table':
        // 简单表格：逐行提取
        buf.push('\\n');
        node.querySelectorAll('tr').forEach(function(tr, ri) {
          var cells = Array.from(tr.querySelectorAll('th, td'))
            .map(function(c) { return c.textContent.trim(); });
          buf.push('| ' + cells.join(' | ') + ' |\\n');
          if (ri === 0) {
            buf.push('|' + cells.map(function() { return ' --- '; }).join('|') + '|\\n');
          }
        });
        buf.push('\\n');
        break;

      default:
        walkChildren(node);
    }
  }

  function walkChildren(node) {
    node.childNodes.forEach(walk);
  }

  walk(el);
  var text = buf.join('').replace(/\\n{3,}/g, '\\n\\n').trim();
  return text;
}
`
