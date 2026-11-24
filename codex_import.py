"""Incrementally index text messages from local Codex rollout logs."""
import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import datetime

BATCH_SIZE = 64
CHECKPOINT_WINDOW = 256


def fingerprint(log, offset):
    log.seek(max(0, offset - CHECKPOINT_WINDOW))
    return hashlib.sha256(log.read(min(offset, CHECKPOINT_WINDOW))).hexdigest()


def message(entry, session, project, offset):
    payload = entry.get("payload")
    if entry.get("type") != "response_item" or not isinstance(payload, dict):
        return None
    role = payload.get("role")
    if payload.get("type") != "message" or role not in ("user", "assistant"):
        return None
    content = payload.get("content")
    if not isinstance(content, list):
        return None
    text = "\n".join(
        part["text"]
        for part in content
        if isinstance(part, dict)
        and part.get("type") in ("input_text", "output_text", "text")
        and isinstance(part.get("text"), str)
    )
    if not text.strip():
        return None

    item_id = payload.get("id")
    identity = [session, role, item_id] if item_id else [session, role, offset, text]
    record_id = "codex-" + hashlib.sha256(json.dumps(identity).encode("ascii")).hexdigest()
    timestamp = entry.get("timestamp")
    metadata = {"source": "codex", "session": session, "role": role}
    if project:
        metadata["project"] = project
    if isinstance(timestamp, str):
        metadata["ts"] = timestamp
        try:
            metadata["epoch"] = int(datetime.fromisoformat(timestamp.replace("Z", "+00:00")).timestamp())
        except (ValueError, OverflowError, OSError):
            pass
    return record_id, (text, metadata)


def write_batch(collection, encode, records):
    if not records:
        return 0
    existing = set(collection.get(ids=list(records), include=[])["ids"])
    pending = [(key, value) for key, value in records.items() if key not in existing]
    if pending:
        texts = [value[0] for _, value in pending]
        collection.add(
            ids=[key for key, _ in pending],
            documents=texts,
            metadatas=[value[1] for _, value in pending],
            embeddings=encode(texts),
        )
    records.clear()
    return len(pending)


def import_log(path, checkpoint, collection, encode):
    offset, session, project = 0, path.stem, ""
    imported = invalid = 0
    records = {}
    with path.open("rb") as log:
        if checkpoint:
            position, digest, saved_session, saved_project = checkpoint
            if fingerprint(log, position) == digest and log.tell() == position:
                offset, session, project = position, saved_session, saved_project
        start = offset
        log.seek(offset)
        while line := log.readline():
            if not line.endswith(b"\n"):
                break  # A live writer may still be appending this line.
            position, offset = offset, log.tell()
            try:
                entry = json.loads(line)
            except ValueError:
                invalid += 1
                continue
            if not isinstance(entry, dict):
                invalid += 1
                continue
            if entry.get("type") == "session_meta":
                payload = entry.get("payload")
                if isinstance(payload, dict):
                    session_id = payload.get("id") or payload.get("session_id")
                    if isinstance(session_id, str) and session_id:
                        session = session_id
                    cwd = payload.get("cwd")
                    if isinstance(cwd, str):
                        project = cwd
                continue
            record = message(entry, session, project, position)
            if record:
                key, value = record
                records[key] = value
            if len(records) >= BATCH_SIZE:
                imported += write_batch(collection, encode, records)
        imported += write_batch(collection, encode, records)
        updated = (offset, fingerprint(log, offset), session, project) if offset != start else None
    return imported, invalid, updated


def import_history(codex_home, state_path, collection, encode):
    paths = sorted(
        path for name in ("sessions", "archived_sessions")
        for path in (codex_home / name).rglob("*.jsonl") if path.is_file()
    )
    imported = invalid = scanned = 0
    collection_id = str(collection.id)
    with closing(sqlite3.connect(state_path)) as state:
        with state:
            state.execute(
                "CREATE TABLE IF NOT EXISTS checkpoints "
                "(collection_id TEXT, path TEXT PRIMARY KEY, offset INTEGER, digest TEXT, session TEXT, project TEXT)"
            )
            state.execute("DELETE FROM checkpoints WHERE collection_id != ?", (collection_id,))
        for path in paths:
            key = str(path)
            checkpoint = state.execute(
                "SELECT offset, digest, session, project FROM checkpoints WHERE path = ?", (key,)
            ).fetchone()
            try:
                added, malformed, updated = import_log(path, checkpoint, collection, encode)
            except FileNotFoundError as error:
                if error.filename != key:
                    raise
                continue  # Codex can move an active log to archived_sessions during import.
            imported += added
            invalid += malformed
            if updated:
                scanned += 1
                with state:
                    state.execute(
                        "INSERT OR REPLACE INTO checkpoints VALUES (?, ?, ?, ?, ?, ?)",
                        (collection_id, key, *updated),
                    )
    return {"files": len(paths), "updated_files": scanned, "imported": imported, "invalid_lines": invalid}
