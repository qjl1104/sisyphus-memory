#!/usr/bin/env python3
"""Sisyphus 语义细节层 — 基于 ChromaDB + sentence-transformers 的语义记忆检索 CLI。

数据持久化在 ~/.omo/chroma/，embedding 模型 all-MiniLM-L6-v2（本地运行）。

运行 memory_tool.py --help 查看命令。
"""
import json
import os
import sys
from contextlib import redirect_stdout
from pathlib import Path

# 尊重用户的 Hugging Face 配置，默认从官方源加载模型。
os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

OMO_HOME = Path(os.environ.get("OMO_HOME") or Path.home() / ".omo").expanduser().resolve()
DB_DIR = OMO_HOME / "chroma"
MODEL_NAME = "all-MiniLM-L6-v2"
COLLECTION_NAME = "sisyphus_memories"

_model = None


def get_model():
    """懒加载 embedding 模型（仅 add/search 需要）。"""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)
    return _model


def get_client():
    import chromadb
    from chromadb.config import Settings

    DB_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(
        path=str(DB_DIR), settings=Settings(anonymized_telemetry=False)
    )


def get_collection():
    return get_client().get_or_create_collection(
        COLLECTION_NAME, metadata={"hnsw:space": "cosine"}
    )


def existing_collection():
    from chromadb.errors import NotFoundError

    if not (DB_DIR / "chroma.sqlite3").is_file():
        return None
    try:
        return get_client().get_collection(COLLECTION_NAME)
    except NotFoundError:
        return None


def encode(texts):
    return get_model().encode(texts, normalize_embeddings=True).tolist()


def cmd_add(args):
    import uuid
    from datetime import datetime
    col = get_collection()
    text = args.content
    emb = encode([text])
    now = datetime.now()
    col.add(
        ids=[uuid.uuid4().hex],
        embeddings=emb,
        documents=[text],
        metadatas=[{
            "role": args.role,
            "session": args.session,
            "ts": now.isoformat(timespec="seconds"),
            "epoch": int(now.timestamp()),
        }],
    )
    print(f"已存入语义库（role={args.role}, session={args.session}）：{text[:80]}")


def search_records(query, limit):
    col = existing_collection()
    total = col.count() if col is not None else 0
    if not total:
        return []
    result = col.query(query_embeddings=encode([query]), n_results=min(limit, total))
    return [
        {
            "id": record_id,
            "score": 1.0 - distance,
            "preview": doc if len(doc) <= 120 else doc[:120] + "…",
            "metadata": metadata or {},
        }
        for record_id, doc, metadata, distance in zip(
            result["ids"][0], result["documents"][0], result["metadatas"][0], result["distances"][0]
        )
    ]


def get_record(record_id):
    col = existing_collection()
    if col is None:
        return None
    result = col.get(ids=[record_id], include=["documents", "metadatas"])
    if not result["ids"]:
        return None
    return {"id": record_id, "text": result["documents"][0], "metadata": result["metadatas"][0] or {}}


def cmd_search(args, empty=False):
    with redirect_stdout(sys.stderr):
        records = [] if empty else search_records(args.query, args.n)
    if args.json:
        print(json.dumps({"results": records}, ensure_ascii=False))
    elif not records:
        print("语义库为空。")
    else:
        for rank, record in enumerate(records, 1):
            meta = record["metadata"]
            print(f"[{rank}] id={record['id']} | score={record['score']:.3f} | {meta.get('ts', '?')} | "
                  f"{meta.get('role', '?')} | session={meta.get('session', '?')}")
            print(f"    {record['preview']}")


def cmd_get(args, empty=False):
    with redirect_stdout(sys.stderr):
        record = None if empty else get_record(args.id)
    if args.json:
        print(json.dumps({"record": record}, ensure_ascii=False))
    elif record is None:
        print(f"找不到记录：{args.id}", file=sys.stderr)
        return 1
    else:
        sys.stdout.write(record["text"])


def cmd_import_codex(args):
    from codex_import import import_history

    codex_home = args.codex_home.expanduser().resolve()
    if not codex_home.is_dir():
        print(f"找不到 Codex 数据目录：{codex_home}", file=sys.stderr)
        return 1
    result = import_history(codex_home, OMO_HOME / "codex-import.sqlite3", get_collection(), encode)
    print(f"日志 {result['files']} 个，推进 {result['updated_files']} 个，新增 {result['imported']} 条。")
    if result["invalid_lines"]:
        print(f"跳过无效 JSONL 行：{result['invalid_lines']}。", file=sys.stderr)


def cmd_mcp(args):
    from memory_mcp import run

    return run(args.transport, args.port)


def cmd_list(args):
    col = get_collection()
    total = col.count()
    if total == 0:
        print("语义库为空。")
        return
    res = col.get(include=["documents", "metadatas"])
    rows = sorted(
        zip(res["documents"], res["metadatas"]),
        key=lambda r: r[1].get("epoch", 0),
        reverse=True,
    )[: args.limit]
    print(f"共 {total} 条，显示最近 {len(rows)} 条：")
    for doc, meta in rows:
        snippet = doc if len(doc) <= 100 else doc[:100] + "…"
        print(f"- [{meta.get('ts', '?')}] ({meta.get('role', '?')}/"
              f"{meta.get('session', '?')}) {snippet}")


def cmd_stats(_args):
    col = get_collection()
    db_file = DB_DIR / "chroma.sqlite3"
    size = db_file.stat().st_size if db_file.exists() else 0
    print(f"条目数: {col.count()}")
    print(f"数据目录: {DB_DIR}")
    print(f"数据库大小: {size / 1024:.1f} KiB")
    print(f"Embedding 模型: {MODEL_NAME}（本地 sentence-transformers）")


def cmd_clear(args):
    if not args.yes:
        if sys.stdin.isatty():
            try:
                ans = input(f"确认清空 {DB_DIR} 中的语义记忆？[y/N] ").strip().lower()
            except EOFError:
                ans = ""
            if ans != "y":
                print("已取消。")
                return
        else:
            print("非交互环境：请使用 clear --yes 确认清空。", file=sys.stderr)
            return 2
    from chromadb.errors import NotFoundError

    try:
        get_client().delete_collection(COLLECTION_NAME)
    except NotFoundError:
        print("语义库为空。")
        return
    print("语义库已清空。")


def main():
    import argparse

    def positive_int(value):
        number = int(value)
        if number < 1:
            raise argparse.ArgumentTypeError("必须是正整数")
        return number

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    p = argparse.ArgumentParser(description="Sisyphus 语义记忆层 CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("add", help="存入一条记忆")
    pa.add_argument("content")
    pa.add_argument("--role", default="user")
    pa.add_argument("--session", default="unknown")
    pa.set_defaults(func=cmd_add)

    ps = sub.add_parser("search", help="语义检索")
    ps.add_argument("query")
    ps.add_argument("--n", type=positive_int, default=5)
    ps.add_argument("--json", action="store_true", help="输出结构化结果")
    ps.set_defaults(func=cmd_search)

    pg = sub.add_parser("get", help="按记录 ID 读取原文")
    pg.add_argument("id")
    pg.add_argument("--json", action="store_true", help="同时输出原文和来源信息")
    pg.set_defaults(func=cmd_get)

    pi = sub.add_parser("import-codex", help="增量导入本地 Codex 会话")
    pi.add_argument("--codex-home", type=Path, default=Path(os.environ.get("CODEX_HOME") or Path.home() / ".codex"))
    pi.set_defaults(func=cmd_import_codex)

    pm = sub.add_parser("mcp", help="启动只读 MCP")
    pm.add_argument("--transport", choices=["stdio", "streamable-http"], default="stdio")
    pm.add_argument("--port", type=positive_int, default=7332, help="HTTP 监听端口")
    pm.set_defaults(func=cmd_mcp)

    pl = sub.add_parser("list", help="列出最近的记忆")
    pl.add_argument("--limit", type=positive_int, default=20)
    pl.set_defaults(func=cmd_list)

    pt = sub.add_parser("stats", help="统计信息")
    pt.set_defaults(func=cmd_stats)

    pc = sub.add_parser("clear", help="清空语义库")
    pc.add_argument("--yes", action="store_true", help="跳过确认")
    pc.set_defaults(func=cmd_clear)

    args = p.parse_args()
    if args.cmd == "mcp":
        return args.func(args)

    from filelock import FileLock, Timeout

    if args.cmd in ("search", "get") and not DB_DIR.is_dir():
        return args.func(args, empty=True)
    OMO_HOME.mkdir(parents=True, exist_ok=True)
    try:
        with FileLock(str(OMO_HOME / "chroma.lock"), timeout=30):
            return args.func(args)
    except Timeout:
        print("记忆库正在使用，请稍后重试。", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
