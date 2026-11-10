#!/usr/bin/env python3
"""Sisyphus 语义细节层 — 基于 ChromaDB + sentence-transformers 的语义记忆检索 CLI。

数据持久化在 ~/.omo/chroma/，embedding 模型 all-MiniLM-L6-v2（本地运行）。

用法：
  memory_tool.py add "内容" --role user --session 会话ID
  memory_tool.py search "查询" --n 5
  memory_tool.py list --limit 20
  memory_tool.py stats
  memory_tool.py clear
"""
import os
import sys
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


def cmd_add(args):
    import uuid
    from datetime import datetime
    col = get_collection()
    text = args.content
    emb = get_model().encode([text], normalize_embeddings=True).tolist()
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


def cmd_search(args):
    col = get_collection()
    total = col.count()
    if total == 0:
        print("语义库为空。")
        return
    q = get_model().encode([args.query], normalize_embeddings=True).tolist()
    res = col.query(query_embeddings=q, n_results=min(args.n, total))
    docs = res["documents"][0]
    metas = res["metadatas"][0]
    dists = res["distances"][0]
    for rank, (doc, meta, dist) in enumerate(zip(docs, metas, dists), 1):
        score = 1.0 - dist  # cosine 距离 → 相似度
        snippet = doc if len(doc) <= 120 else doc[:120] + "…"
        print(f"[{rank}] score={score:.3f} | {meta.get('ts', '?')} | "
              f"{meta.get('role', '?')} | session={meta.get('session', '?')}")
        print(f"    {snippet}")


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
    ps.set_defaults(func=cmd_search)

    pl = sub.add_parser("list", help="列出最近的记忆")
    pl.add_argument("--limit", type=positive_int, default=20)
    pl.set_defaults(func=cmd_list)

    pt = sub.add_parser("stats", help="统计信息")
    pt.set_defaults(func=cmd_stats)

    pc = sub.add_parser("clear", help="清空语义库")
    pc.add_argument("--yes", action="store_true", help="跳过确认")
    pc.set_defaults(func=cmd_clear)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
