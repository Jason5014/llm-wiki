"""
LLM + Embedding 客户端 — 统一使用 DashScope OpenAI 兼容接口
"""
import asyncio
import json
import re
from typing import Any

from openai import AsyncOpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

from src.config import settings


# ─────────────────────────────────────────────
# 客户端单例
# ─────────────────────────────────────────────

def get_client() -> AsyncOpenAI:
    """获取 DashScope OpenAI 兼容客户端"""
    return AsyncOpenAI(
        api_key=settings.dashscope_api_key,
        base_url=settings.dashscope_base_url,
    )


# 全局客户端（延迟初始化）
_client: AsyncOpenAI | None = None


def client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = get_client()
    return _client


# ─────────────────────────────────────────────
# LLM 调用
# ─────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def chat_completion(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.3,
    max_tokens: int = 4096,
) -> str:
    """
    调用 LLM 聊天接口，返回文本内容
    自动重试 3 次（指数退避）
    """
    model = model or settings.llm_model
    response = await client().chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
    )
    return response.choices[0].message.content or ""


async def chat_json(
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.1,
) -> dict[str, Any] | list[Any]:
    """
    调用 LLM 并解析 JSON 响应
    若 LLM 返回包裹在 ```json ... ``` 中的内容也能正确解析
    """
    raw = await chat_completion(messages, model=model, temperature=temperature)
    return extract_json(raw)


def extract_json(text: str) -> dict[str, Any] | list[Any]:
    """
    从 LLM 输出中提取 JSON 数据
    支持裸 JSON、```json...``` 包裹的格式
    """
    # 尝试提取 ```json...``` 代码块
    code_block = re.search(r"```(?:json)?\s*\n([\s\S]*?)\n```", text)
    if code_block:
        text = code_block.group(1)

    # 尝试直接解析
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # 提取第一个完整的 JSON 对象或数组
    for pattern in (r"\{[\s\S]*\}", r"\[[\s\S]*\]"):
        m = re.search(pattern, text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                continue

    raise ValueError(f"无法从 LLM 输出中提取 JSON：{text[:200]}...")


# ─────────────────────────────────────────────
# Embedding
# ─────────────────────────────────────────────

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def embed_texts(texts: list[str]) -> list[list[float]]:
    """
    批量向量化文本
    DashScope 单次最多 25 条
    """
    if not texts:
        return []

    response = await client().embeddings.create(
        model=settings.embedding_model,
        input=texts,
    )
    # 按 index 排序，返回向量列表
    results = sorted(response.data, key=lambda x: x.index)
    return [item.embedding for item in results]


async def embed_texts_batched(texts: list[str], batch_size: int | None = None) -> list[list[float]]:
    """
    大批量向量化（自动分批处理）
    """
    batch_size = batch_size or settings.embed_batch_size
    if not texts:
        return []

    all_vectors = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        vectors = await embed_texts(batch)
        all_vectors.extend(vectors)
        # 避免频率限制
        if i + batch_size < len(texts):
            await asyncio.sleep(0.5)

    return all_vectors


async def embed_single(text: str) -> list[float]:
    """向量化单条文本"""
    vectors = await embed_texts([text])
    return vectors[0]


# ─────────────────────────────────────────────
# 并发控制器
# ─────────────────────────────────────────────

class RateLimitedExecutor:
    """限制并发的异步执行器"""

    def __init__(self, max_concurrent: int | None = None):
        max_c = max_concurrent or settings.llm_max_concurrent
        self._semaphore = asyncio.Semaphore(max_c)

    async def run(self, coro):
        async with self._semaphore:
            return await coro


# 全局 LLM 执行器
llm_executor = RateLimitedExecutor()
