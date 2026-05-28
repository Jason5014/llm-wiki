"""
Stage 3b: Wiki 页面生成
将实体/概念数据生成完整的 Markdown Wiki 页面
"""
import asyncio
import logging
from datetime import datetime

from src.config import settings
from src.llm import chat_completion, llm_executor
from src.models import ConceptData, EntityData
from src.storage import (
    concept_page_exists,
    entity_page_exists,
    load_wiki_page,
    save_wiki_page,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# Entity 页面生成
# ─────────────────────────────────────────────

ENTITY_SYSTEM_PROMPT = """你是知识库条目撰写专家，风格：简洁、专业、百科全书式。

生成完整的 Markdown Wiki 页面，严格遵循以下格式：

```
---
type: entity
category: {category}
aliases: {aliases_json}
tags: []
updated: {today}
---

# {name}

> {description}

## 概述
（2-3段综合介绍，基于给定的上下文内容）

## 核心特性
- **特性1**：说明
- **特性2**：说明

## 典型应用场景
- 场景1
- 场景2

## 关联关系
- **所属公司/项目**：[[Parent]]（如有）
- **相关实体**：[[Entity1]]、[[Entity2]]
- **核心概念**：[[Concept1]]、[[Concept2]]

## 参考来源
- [[source/doc_id_1]]
- [[source/doc_id_2]]
```

要求：
1. [[WikiLink]] 格式引用所有实体和概念（不要加路径前缀，只写名称）
2. 基于提供的上下文，保持事实准确
3. 中文撰写，专业名词保留英文
4. 不要输出格式说明，直接输出完整 Markdown"""

ENTITY_USER_PROMPT_TEMPLATE = """请为以下实体生成 Wiki 页面：

**实体信息：**
- 名称：{name}
- 类别：{category}
- 描述：{description}
- 别名：{aliases}
- 相关实体：{related_entities}
- 关联概念：{related_concepts}
- 今日日期：{today}

**相关文章上下文：**
{context}"""


# ─────────────────────────────────────────────
# Concept 页面生成
# ─────────────────────────────────────────────

CONCEPT_SYSTEM_PROMPT = """你是知识库条目撰写专家，风格：简洁、专业、百科全书式。

生成完整的 Markdown Wiki 页面，严格遵循以下格式：

```
---
type: concept
category: {category}
aliases: {aliases_json}
tags: []
updated: {today}
---

# {name}

> {description}

## 定义
（精确定义，1-2段）

## 核心原理
（工作原理解释）

## 优势与局限
**优势**
- ...

**局限**
- ...

## 典型应用
- 场景1：[[Entity1]] 中的应用
- 场景2：与 [[concept2]] 结合使用

## 相关概念
- [[RelatedConcept1]] — 关系说明

## 参考来源
- [[source/doc_id_1]]
```

要求：
1. [[WikiLink]] 格式引用所有实体和概念
2. 基于提供的上下文，保持事实准确
3. 中文撰写，专业名词保留英文
4. 不要输出格式说明，直接输出完整 Markdown"""

CONCEPT_USER_PROMPT_TEMPLATE = """请为以下概念生成 Wiki 页面：

**概念信息：**
- 名称：{name}
- 类别：{category}
- 描述：{description}
- 别名：{aliases}
- 相关概念：{related_concepts}
- 关联实体：{related_entities}
- 今日日期：{today}

**相关文章上下文：**
{context}"""


# ─────────────────────────────────────────────
# 核心生成函数
# ─────────────────────────────────────────────

def _build_context(kb_id: str, source_docs: list[str], max_chars: int = 3000) -> str:
    """从 source 文档中构建上下文（截取前 max_chars 字符）"""
    parts = []
    total_chars = 0
    for doc_id in source_docs[:5]:  # 最多取 5 篇
        content = load_wiki_page(kb_id, "source", doc_id)
        if content:
            excerpt = content[:800]
            parts.append(f"[{doc_id}]\n{excerpt}")
            total_chars += len(excerpt)
            if total_chars >= max_chars:
                break
    return "\n\n---\n\n".join(parts) if parts else "（暂无相关文章上下文）"


async def build_entity_page(
    kb_id: str,
    entity: EntityData,
    force: bool = False,
) -> str | None:
    """
    生成实体 Wiki 页面
    Returns: 生成的 Markdown 内容，None 表示跳过
    """
    if not force and entity_page_exists(kb_id, entity.name):
        logger.debug(f"跳过实体（已存在）：{entity.name}")
        return None

    today = datetime.now().strftime("%Y-%m-%d")
    context = _build_context(kb_id, entity.source_docs)

    try:
        content = await llm_executor.run(
            chat_completion(
                messages=[
                    {"role": "system", "content": ENTITY_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": ENTITY_USER_PROMPT_TEMPLATE.format(
                            name=entity.name,
                            category=entity.category,
                            description=entity.description,
                            aliases=", ".join(entity.aliases) or "无",
                            related_entities=", ".join(entity.related_entities) or "无",
                            related_concepts=", ".join(entity.related_concepts) or "无",
                            today=today,
                            context=context,
                        ),
                    },
                ],
                model=settings.llm_model,
            )
        )
    except Exception as e:
        logger.error(f"实体页面生成失败（{entity.name}）：{e}")
        return None

    await save_wiki_page(kb_id, "entity", entity.name, content)
    logger.info(f"✅ 实体页面生成：{entity.name}")
    return content


async def build_concept_page(
    kb_id: str,
    concept: ConceptData,
    force: bool = False,
) -> str | None:
    """
    生成概念 Wiki 页面
    Returns: 生成的 Markdown 内容，None 表示跳过
    """
    if not force and concept_page_exists(kb_id, concept.name):
        logger.debug(f"跳过概念（已存在）：{concept.name}")
        return None

    today = datetime.now().strftime("%Y-%m-%d")
    context = _build_context(kb_id, concept.source_docs)

    try:
        content = await llm_executor.run(
            chat_completion(
                messages=[
                    {"role": "system", "content": CONCEPT_SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": CONCEPT_USER_PROMPT_TEMPLATE.format(
                            name=concept.name,
                            category=concept.category,
                            description=concept.description,
                            aliases=", ".join(concept.aliases) or "无",
                            related_concepts=", ".join(concept.related_concepts) or "无",
                            related_entities=", ".join(concept.related_entities) or "无",
                            today=today,
                            context=context,
                        ),
                    },
                ],
                model=settings.llm_model,
            )
        )
    except Exception as e:
        logger.error(f"概念页面生成失败（{concept.name}）：{e}")
        return None

    await save_wiki_page(kb_id, "concept", concept.name, content)
    logger.info(f"✅ 概念页面生成：{concept.name}")
    return content


async def build_all_pages(
    kb_id: str,
    entities: list[EntityData],
    concepts: list[ConceptData],
    force: bool = False,
    progress_callback=None,
) -> None:
    """批量生成所有实体和概念页面"""
    total = len(entities) + len(concepts)
    completed = 0
    semaphore = asyncio.Semaphore(settings.llm_max_concurrent)

    async def _build_with_sem(coro, name: str):
        nonlocal completed
        async with semaphore:
            result = await coro
            completed += 1
            if progress_callback:
                await progress_callback(
                    completed, total, f"{'✅' if result else '⏭️'} {name}"
                )

    tasks = []
    for entity in entities:
        tasks.append(_build_with_sem(build_entity_page(kb_id, entity, force), f"实体：{entity.name}"))
    for concept in concepts:
        tasks.append(_build_with_sem(build_concept_page(kb_id, concept, force), f"概念：{concept.name}"))

    await asyncio.gather(*tasks, return_exceptions=True)
    logger.info(f"页面生成完成，共 {total} 个")
