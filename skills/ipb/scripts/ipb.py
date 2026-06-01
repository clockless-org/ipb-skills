#!/usr/bin/env python3
"""Log and report Interruptions Per Billion Tokens (IPB)."""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

BILLION = 1_000_000_000
DEFAULT_LOG = Path(".ipb/events.jsonl")


@dataclass(frozen=True)
class Level:
    code: str
    name: str
    min_ipb: float
    max_ipb: float
    summary: str


LEVELS = [
    Level("L1", "Manual AI operation", 3000, math.inf, "Humans are still driving the workflow."),
    Level("L2", "Skilled tool use", 1000, 3000, "Task delegation works, but humans intervene frequently."),
    Level("L3", "Async delegation", 300, 1000, "Batched agent work exists, but review and routing remain heavy."),
    Level("L4", "Agentic workflow", 50, 300, "Task state, auto retry, and verification reduce interruptions."),
    Level("L5", "AI-native system", 0, 50, "Humans mostly handle goals, boundaries, exceptions, and final judgment."),
]

TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "reasoning_tokens",
)


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def append_event(path: Path, event: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    event.setdefault("ts", now_iso())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")


def read_events(paths: Iterable[Path]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for path in paths:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, 1):
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise SystemExit(f"{path}:{line_no}: invalid JSON: {exc}") from exc
    return events


def event_tokens(event: dict[str, Any]) -> int:
    if event.get("type") not in {"usage", "tokens", "run"}:
        return 0
    for key in ("tokens", "total_tokens"):
        value = event.get(key)
        if isinstance(value, (int, float)):
            return max(0, int(value))
    total = 0
    for key in TOKEN_FIELDS:
        value = event.get(key)
        if isinstance(value, (int, float)):
            total += max(0, int(value))
    return total


def event_interruptions(event: dict[str, Any]) -> float:
    if event.get("type") not in {"interruption", "human_interruption"}:
        return 0
    if event.get("counted") is False:
        return 0
    count = event.get("count", 1)
    if not isinstance(count, (int, float)):
        return 1
    return max(0, float(count))


def classify(ipb: float) -> Level:
    for level in LEVELS:
        if level.min_ipb <= ipb < level.max_ipb:
            return level
    return LEVELS[-1]


def summarize(events: list[dict[str, Any]]) -> dict[str, Any]:
    tokens = sum(event_tokens(event) for event in events)
    interruptions = sum(event_interruptions(event) for event in events)
    ipb = None if tokens <= 0 else interruptions / (tokens / BILLION)
    level = None if ipb is None else classify(ipb)
    result: dict[str, Any] = {
        "tokens": tokens,
        "interruptions": interruptions,
        "ipb": ipb,
        "level": asdict(level) if level else None,
    }
    if ipb is not None and ipb < 5:
        result["badge"] = "AI factory-like"
    return result


def print_report(summary: dict[str, Any]) -> None:
    tokens = summary["tokens"]
    interruptions = summary["interruptions"]
    ipb = summary["ipb"]
    print("IPB Report")
    print(f"tokens: {tokens:,}")
    print(f"interruptions: {interruptions:g}")
    if ipb is None:
        print("IPB: unavailable (no token usage recorded)")
        return
    level = summary["level"]
    print(f"IPB: {ipb:,.2f}")
    print(f"level: {level['code']} - {level['name']}")
    print(f"summary: {level['summary']}")
    if summary.get("badge"):
        print(f"badge: {summary['badge']}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Measure Interruptions Per Billion Tokens (IPB).")
    parser.add_argument("--log", action="append", type=Path, default=None, help="JSONL event log path; repeatable.")
    sub = parser.add_subparsers(dest="command", required=True)

    usage = sub.add_parser("log-usage", help="Append a token usage event.")
    usage.add_argument("--tokens", type=int, default=None, help="Total tokens for this event.")
    usage.add_argument("--input-tokens", type=int, default=0)
    usage.add_argument("--output-tokens", type=int, default=0)
    usage.add_argument("--provider", default="")
    usage.add_argument("--model", default="")
    usage.add_argument("--task-id", default="")

    interruption = sub.add_parser("log-interruption", help="Append a human interruption event.")
    interruption.add_argument("--reason", required=True)
    interruption.add_argument("--note", default="")
    interruption.add_argument("--task-id", default="")
    interruption.add_argument("--count", type=float, default=1)

    report = sub.add_parser("report", help="Report IPB from event logs.")
    report.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")

    classify_cmd = sub.add_parser("classify", help="Classify a raw IPB value.")
    classify_cmd.add_argument("ipb", type=float)
    classify_cmd.add_argument("--json", action="store_true")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    logs = args.log or [DEFAULT_LOG]
    primary_log = logs[0]

    if args.command == "log-usage":
        event: dict[str, Any] = {"type": "usage"}
        if args.tokens is not None:
            event["tokens"] = args.tokens
        else:
            event["input_tokens"] = args.input_tokens
            event["output_tokens"] = args.output_tokens
        if args.provider:
            event["provider"] = args.provider
        if args.model:
            event["model"] = args.model
        if args.task_id:
            event["task_id"] = args.task_id
        append_event(primary_log, event)
        print(f"logged usage to {primary_log}")
        return 0

    if args.command == "log-interruption":
        event = {"type": "interruption", "reason": args.reason, "count": args.count}
        if args.note:
            event["note"] = args.note
        if args.task_id:
            event["task_id"] = args.task_id
        append_event(primary_log, event)
        print(f"logged interruption to {primary_log}")
        return 0

    if args.command == "report":
        result = summarize(read_events(logs))
        if args.json:
            print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print_report(result)
        return 0

    if args.command == "classify":
        level = classify(args.ipb)
        payload = asdict(level)
        if args.ipb < 5:
            payload["badge"] = "AI factory-like"
        if args.json:
            print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
        else:
            print(f"{level.code} - {level.name}: {level.summary}")
            if args.ipb < 5:
                print("badge: AI factory-like")
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
