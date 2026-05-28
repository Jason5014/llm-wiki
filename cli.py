"""
LLM Wiki CLI — 命令行入口
"""
import asyncio
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

app = typer.Typer(name="llm-wiki", help="AI 驱动的 LLM Wiki 知识图谱系统")
console = Console()


# ─────────────────────────────────────────────
# 知识库管理
# ─────────────────────────────────────────────

@app.command("list", help="列出所有知识库")
def list_kbs():
    from src.models import KBConfig
    from src.storage import get_kb_stats, list_kb_ids, load_kb_config

    ids = list_kb_ids()
    if not ids:
        console.print("[yellow]暂无知识库，使用 'llm-wiki create' 创建[/yellow]")
        return

    table = Table(title="知识库列表")
    table.add_column("ID", style="cyan")
    table.add_column("名称", style="white")
    table.add_column("Raw 文档", justify="right")
    table.add_column("Entity", justify="right")
    table.add_column("Concept", justify="right")
    table.add_column("已索引", justify="center")

    for kb_id in ids:
        config = load_kb_config(kb_id)
        stats = get_kb_stats(kb_id)
        if config:
            table.add_row(
                kb_id,
                config.name,
                str(stats.raw_count),
                str(stats.entity_count),
                str(stats.concept_count),
                "✅" if stats.indexed else "❌",
            )

    console.print(table)


@app.command("create", help="创建新知识库")
def create_kb(
    kb_id: str = typer.Argument(..., help="知识库 ID（字母/数字/连字符）"),
    name: str = typer.Option(..., "--name", "-n", help="显示名称"),
    domain: str = typer.Option("", "--domain", "-d", help="领域标签"),
    description: str = typer.Option("", "--desc", help="简介"),
):
    from src.models import KBConfig, KBStatus
    from src.storage import init_kb_dirs, load_kb_config, save_kb_config

    if load_kb_config(kb_id):
        console.print(f"[red]知识库 '{kb_id}' 已存在[/red]")
        raise typer.Exit(1)

    from datetime import datetime
    config = KBConfig(
        kb_id=kb_id,
        name=name,
        domain=domain,
        description=description,
        status=KBStatus.ready,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    init_kb_dirs(kb_id)
    save_kb_config(config)
    console.print(f"[green]✅ 知识库 '{kb_id}' 创建成功[/green]")


# ─────────────────────────────────────────────
# 数据采集
# ─────────────────────────────────────────────

@app.command("collect", help="导入本地文件到知识库")
def collect(
    kb_id: str = typer.Argument(..., help="目标知识库 ID"),
    file: Optional[Path] = typer.Option(None, "--file", "-f", help="导入单个文件"),
    dir: Optional[Path] = typer.Option(None, "--dir", "-d", help="导入整个目录"),
):
    from src.storage import load_kb_config

    if not load_kb_config(kb_id):
        console.print(f"[red]知识库 '{kb_id}' 不存在[/red]")
        raise typer.Exit(1)

    files_to_import: list[Path] = []

    if file:
        if not file.exists():
            console.print(f"[red]文件不存在：{file}[/red]")
            raise typer.Exit(1)
        files_to_import.append(file)

    if dir:
        if not dir.is_dir():
            console.print(f"[red]目录不存在：{dir}[/red]")
            raise typer.Exit(1)
        for ext in ("*.md", "*.txt", "*.pdf", "*.html"):
            files_to_import.extend(dir.glob(ext))

    if not files_to_import:
        console.print("[yellow]未找到可导入的文件[/yellow]")
        return

    async def _import():
        from datetime import datetime
        from src.models import RawDocument
        from src.storage import save_raw_document

        for f in files_to_import:
            data = f.read_bytes()
            # 简单提取文本
            try:
                content = data.decode("utf-8", errors="ignore")
            except Exception:
                content = str(data)

            title = f.stem.replace("-", " ").replace("_", " ")
            doc = RawDocument(
                title=title,
                url=f"file://{f.absolute()}",
                content=content,
                metadata={"source": "cli-import", "filename": f.name},
                crawled_at=datetime.now(),
            )
            doc_id = await save_raw_document(kb_id, doc)
            console.print(f"  [green]✅[/green] {f.name} → {doc_id}")

    console.print(f"导入 {len(files_to_import)} 个文件到 [cyan]{kb_id}[/cyan]...")
    asyncio.run(_import())
    console.print(f"[green]导入完成[/green]")


# ─────────────────────────────────────────────
# 处理流水线
# ─────────────────────────────────────────────

@app.command("process", help="运行处理流水线")
def process(
    kb_id: str = typer.Argument(..., help="目标知识库 ID"),
    stage: str = typer.Option("all", "--stage", "-s", help="阶段：all|source|extract|pages|index"),
    force: bool = typer.Option(False, "--force", help="强制重新处理（忽略已处理的文件）"),
):
    from src.storage import load_kb_config

    if not load_kb_config(kb_id):
        console.print(f"[red]知识库 '{kb_id}' 不存在[/red]")
        raise typer.Exit(1)

    console.print(f"开始处理知识库 [cyan]{kb_id}[/cyan]，阶段：[yellow]{stage}[/yellow]")

    async def _run():
        from src.models import PipelineStage, RunPipelineRequest
        from src.pipeline import _execute_pipeline, create_task

        req = RunPipelineRequest(
            stage=PipelineStage(stage),
            force=force,
        )
        task = create_task(kb_id, stage)

        async def progress(completed: int, total: int, message: str = "") -> None:
            console.print(f"  [{completed}/{total}] {message}")

        # 直接执行（CLI 不需要后台异步）
        from src.pipeline import _execute_pipeline
        await _execute_pipeline(task, req)

        if task.status.value == "done":
            console.print(f"\n[green]✅ 处理完成！[/green]")
        else:
            console.print(f"\n[red]❌ 处理失败：{task.message}[/red]")

    asyncio.run(_run())


# ─────────────────────────────────────────────
# 搜索
# ─────────────────────────────────────────────

@app.command("search", help="在知识库中搜索")
def search_cmd(
    kb_id: str = typer.Argument(..., help="知识库 ID"),
    query: str = typer.Argument(..., help="搜索查询"),
    no_answer: bool = typer.Option(False, "--no-answer", help="只检索，不生成答案"),
):
    from src.storage import load_kb_config

    if not load_kb_config(kb_id):
        console.print(f"[red]知识库 '{kb_id}' 不存在[/red]")
        raise typer.Exit(1)

    async def _search():
        from src.retriever.retriever import search
        result = await search(kb_id, query, generate_answer_flag=not no_answer)

        if result.answer:
            console.print("\n[bold]AI 回答：[/bold]")
            console.print(result.answer)

        console.print(f"\n[bold]引用来源（{len(result.sources)} 条）：[/bold]")
        for src in result.sources:
            console.print(f"  [{src.score:.3f}] {src.path} — {src.snippet[:80]}")

        console.print(f"\n搜索耗时：{result.search_time_ms:.0f}ms")

    asyncio.run(_search())


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────

if __name__ == "__main__":
    app()
