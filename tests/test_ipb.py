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


if __name__ == "__main__":
    unittest.main()
