import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import chromadb

from codex_import import import_history


def event(event_type, **payload):
    return json.dumps({"type": event_type, "payload": payload}).encode() + b"\n"


def message(text, item_id=None, role="user"):
    return event(
        "response_item", type="message", id=item_id, role=role,
        content=[{"type": "input_text", "text": text}],
    )


def encode(texts):
    return [[1.0, 0.0] for _ in texts]


class CodexImportTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.home = Path(directory.name)
        self.state = self.home / "import.sqlite3"
        self.log = self.home / "sessions" / "rollout-test.jsonl"
        self.log.parent.mkdir()
        self.client = chromadb.EphemeralClient()
        self.collection = self.client.create_collection("test-" + self.home.name)

    def sync(self, encoder=encode):
        return import_history(self.home, self.state, self.collection, encoder)

    def test_incremental_import_and_archive_deduplicate(self):
        tail = message("后续原文", role="assistant")
        self.log.write_bytes(
            event("session_meta", id="thread-1", cwd="/test/project")
            + message("初始原文", "item-1")
            + message("忽略这条开发者指令", role="developer")
            + event("event_msg", type="user_message", message="初始原文")
            + tail[:15]
        )
        self.assertEqual(self.sync()["imported"], 1)
        self.assertEqual(self.sync()["updated_files"], 0)

        with self.log.open("ab") as log:
            log.write(tail[15:] + message("初始原文", "item-1"))
        self.assertEqual(self.sync()["imported"], 1)
        archive = self.home / "archived_sessions" / self.log.name
        archive.parent.mkdir()
        self.log.rename(archive)
        self.assertEqual(self.sync()["imported"], 0)

        records = self.collection.get()
        self.assertCountEqual(records["documents"], ["初始原文", "后续原文"])
        self.assertTrue(all(meta["project"] == "/test/project" for meta in records["metadatas"]))

    def test_interrupted_import_retries_without_duplicates(self):
        self.log.write_bytes(message("first") + message("second"))

        def fail_on_second_batch(texts):
            if texts == ["second"]:
                raise RuntimeError("simulated embedding failure")
            return encode(texts)

        with patch("codex_import.BATCH_SIZE", 1):
            with self.assertRaisesRegex(RuntimeError, "simulated"):
                self.sync(fail_on_second_batch)
            self.assertEqual(self.collection.count(), 1)
            self.assertEqual(self.sync()["imported"], 1)
        self.assertCountEqual(self.collection.get()["documents"], ["first", "second"])


if __name__ == "__main__":
    unittest.main()
