import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "skills" / "ipb" / "scripts" / "ipb.py"
spec = importlib.util.spec_from_file_location("ipb", MODULE_PATH)
ipb = importlib.util.module_from_spec(spec)
assert spec.loader is not None
sys.modules[spec.name] = ipb
spec.loader.exec_module(ipb)


class IPBTests(unittest.TestCase):
    def test_classification_boundaries(self):
        self.assertEqual(ipb.classify(3500).code, "L1")
        self.assertEqual(ipb.classify(1500).code, "L2")
        self.assertEqual(ipb.classify(500).code, "L3")
        self.assertEqual(ipb.classify(100).code, "L4")
        self.assertEqual(ipb.classify(10).code, "L5")

    def test_summarize_counts_tokens_and_interruptions(self):
        events = [
            {"type": "usage", "tokens": 2_000_000_000},
            {"type": "usage", "input_tokens": 500_000_000, "output_tokens": 500_000_000},
            {"type": "interruption", "count": 9},
        ]
        result = ipb.summarize(events)
        self.assertEqual(result["tokens"], 3_000_000_000)
        self.assertEqual(result["interruptions"], 9)
        self.assertEqual(result["ipb"], 3)
        self.assertEqual(result["level"]["code"], "L5")
        self.assertEqual(result["badge"], "AI factory-like")

    def test_jsonl_reader(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "events.jsonl"
            path.write_text(
                "\n".join(
                    [
                        json.dumps({"type": "usage", "tokens": 1_000_000_000}),
                        json.dumps({"type": "interruption", "reason": "manual-retry"}),
                    ]
                ),
                encoding="utf-8",
            )
            result = ipb.summarize(ipb.read_events([path]))
            self.assertEqual(result["ipb"], 1)

    def test_imports_claude_usage_and_human_messages(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claude.jsonl"
            out = Path(tmp) / "events.jsonl"
            records = [
                {"type": "user", "message": {"role": "user", "content": "initial task"}},
                {
                    "type": "assistant",
                    "message": {
                        "role": "assistant",
                        "usage": {
                            "input_tokens": 10,
                            "cache_read_input_tokens": 4,
                            "output_tokens": 6,
                        },
                    },
                },
                {"type": "user", "message": {"role": "user", "content": [{"type": "tool_result"}]}},
                {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "blocked"}]}},
            ]
            path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")

            stats = ipb.import_source("claude", [path], out)
            self.assertEqual(stats.tokens, 20)
            self.assertEqual(stats.user_messages, 2)
            self.assertEqual(stats.interruptions, 2)
            self.assertEqual(ipb.summarize(ipb.read_events([out]))["ipb"], 100_000_000)

    def test_import_can_exclude_first_user_message(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "claude.jsonl"
            records = [
                {"type": "user", "message": {"role": "user", "content": "initial task"}},
                {"type": "user", "message": {"role": "user", "content": "follow up"}},
            ]
            path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")

            stats = ipb.import_source(
                "claude",
                [path],
                Path(tmp) / "events.jsonl",
                dry_run=True,
                exclude_first_user_message=True,
            )
            self.assertEqual(stats.user_messages, 2)
            self.assertEqual(stats.interruptions, 1)

    def test_claude_subagent_user_messages_are_internal(self):
        with tempfile.TemporaryDirectory() as tmp:
            subagents = Path(tmp) / "subagents"
            subagents.mkdir()
            path = subagents / "agent.jsonl"
            records = [
                {"type": "user", "message": {"role": "user", "content": [{"type": "text", "text": "delegate"}]}},
                {"type": "assistant", "message": {"role": "assistant", "usage": {"input_tokens": 10, "output_tokens": 5}}},
            ]
            path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")

            stats = ipb.import_source("claude", [path], Path(tmp) / "events.jsonl", dry_run=True)
            self.assertEqual(stats.tokens, 15)
            self.assertEqual(stats.user_messages, 0)
            self.assertEqual(stats.interruptions, 0)

    def test_imports_codex_incremental_token_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "codex.jsonl"
            out = Path(tmp) / "events.jsonl"
            records = [
                {"type": "event_msg", "payload": {"type": "user_message"}},
                {
                    "type": "event_msg",
                    "payload": {
                        "type": "token_count",
                        "info": {
                            "last_token_usage": {"total_tokens": 100},
                            "total_token_usage": {"total_tokens": 10_000},
                        },
                    },
                },
                {"type": "response_item", "payload": {"type": "message", "role": "user"}},
                {"type": "event_msg", "payload": {"type": "user_message"}},
            ]
            path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")

            stats = ipb.import_source("codex", [path], out)
            self.assertEqual(stats.tokens, 100)
            self.assertEqual(stats.user_messages, 2)
            self.assertEqual(stats.interruptions, 2)

    def test_imports_generic_hermes_style_records(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "hermes.jsonl"
            records = [
                {"role": "user", "content": "initial task"},
                {"usage": {"input_tokens": 40, "output_tokens": 10}},
                {"payload": {"type": "user_message"}},
            ]
            path.write_text("\n".join(json.dumps(record) for record in records), encoding="utf-8")

            stats = ipb.import_source("hermes", [path], Path(tmp) / "events.jsonl", dry_run=True)
            self.assertEqual(stats.tokens, 50)
            self.assertEqual(stats.user_messages, 2)
            self.assertEqual(stats.interruptions, 2)


if __name__ == "__main__":
    unittest.main()
