"""
Tier0 机械质检门禁 — 基于规则的快速质量检查

检查项：
  1. 文本长度完整性（与预期最短长度比较）
  2. 标题有效性（非空、不等于 URL）
  3. 截断检测（末尾是否为不完整片段）
  4. 登录墙 / 验证码检测
  5. 图片完整性比例（如有图片预期）

返回：
  {
    "score": float,           # 综合质量分 0~1
    "tier": 0,
    "completeness": {
      "text": float,          # 文本完整性分
      "images": float,        # 图片完整性分
    },
    "issues": list[str],      # 问题标识列表
    "action": "passed" | "re_extract",
  }
"""
import re


# 常见截断标记（中英文）
_TRUNCATION_PATTERNS = [
    r"…\s*$",
    r"\.\.\.\s*$",
    r"更多\s*$",
    r"展开全文\s*$",
    r"查看全部\s*$",
    r"Read more\s*$",
    r"Continue reading\s*$",
    r"\[truncated\]\s*$",
]

# 登录墙 / 验证码特征（仅匹配明确的拦截场景，避免误判正常页面）
_BLOCKED_PATTERNS = [
    r"登录后查看",
    r"请登录后",
    r"需要登录",
    r"请先登录",
    r"验证码",
    r"access denied",
    r"please log ?in",
    r"captcha",
    r"verify you are human",
    r"请完成验证",
    r"账号登录",
    r"请使用微信客户端打开",
]


def tier0_inspect(
    doc: dict,
    *,
    expected_min_len: int = 500,
) -> dict:
    """
    Tier0 机械质检。

    Args:
        doc: 文档字典，需包含 title / content / url 字段
        expected_min_len: 该页面预期的最短字符数（默认 500）

    Returns:
        质检结果字典
    """
    text = doc.get("content", "") or ""
    title = doc.get("title", "") or ""
    url = doc.get("url", "") or ""
    metadata = doc.get("metadata", {}) or {}
    page_meta_img_count = metadata.get("img_count", 0)

    issues: list[str] = []

    # ── 1. 文本长度完整性 ──────────────────────
    text_score = min(len(text) / max(expected_min_len, 1), 1.0)
    if len(text) < expected_min_len * 0.3:
        issues.append("too_short")

    # ── 2. 标题有效性 ──────────────────────────
    if not title.strip():
        issues.append("bad_title")
    elif title.strip() == url.strip():
        issues.append("bad_title")

    # ── 3. 截断检测 ────────────────────────────
    for pat in _TRUNCATION_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            issues.append("truncated")
            break

    # ── 4. 登录墙 / 验证码检测 ─────────────────
    for pat in _BLOCKED_PATTERNS:
        if re.search(pat, text, re.IGNORECASE):
            issues.append("blocked")
            break

    # ── 5. 图片完整性 ──────────────────────────
    has_imgs = page_meta_img_count > 0
    if has_imgs:
        # 统计 markdown 中的图片数量
        actual_img_count = text.count("![")
        images_score = min(actual_img_count / page_meta_img_count, 1.0)
        if images_score < 0.8:
            issues.append("images_missing")
    else:
        images_score = 1.0

    # ── 综合评分 ───────────────────────────────
    score = min(text_score, images_score)

    # ── 决策 action ────────────────────────────
    if not issues:
        action = "passed"
    elif "blocked" in issues:
        # 登录墙/验证码：重提取无意义，需要用户手动干预
        action = "blocked"
    else:
        action = "re_extract"

    return {
        "score": round(score, 2),
        "tier": 0,
        "completeness": {
            "text": round(text_score, 2),
            "images": round(images_score, 2),
        },
        "issues": issues,
        "action": action,
    }
