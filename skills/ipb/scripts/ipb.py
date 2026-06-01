#!/usr/bin/env python3
"""Log and report Interruptions Per Billion Tokens (IPB)."""

from __future__ import annotations

import argparse
import glob
import json
import math
import os
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


@dataclass
class ImportStats:
    source: str
    files: int = 0
    records: int = 0
    token_events: int = 0
    tokens: int = 0
    user_messages: int = 0
    interruptions: float = 0
    parse_errors: int = 0


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
    "cached_input_tokens",
    "cache_read_tokens",
    "cache_write_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
    "reasoning_tokens",
    "reasoning_output_tokens",
)

SOURCE_DEFAULTS = {
    "claude": ("~/.claude/projects/**/*.jsonl",),
    "codex": ("~/.codex/sessions/**/*.jsonl", "~/.codex/archived_sessions/*.jsonl"),
    "hermes": (
        "~/.hermes/**/*.jsonl",
        "~/.config/hermes/**/*.jsonl",
        "~/Library/Application Support/Hermes/**/*.jsonl",
        "~/Library/Application Support/hermes/**/*.jsonl",
    ),
}


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


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def usage_dict_tokens(usage: dict[str, Any]) -> int:
    for key in ("tokens", "total_tokens"):
        value = usage.get(key)
        if is_number(value):
            return max(0, int(value))
    total = 0
    for key in TOKEN_FIELDS:
        value = usage.get(key)
        if is_number(value):
            total += max(0, int(value))
    return total


def event_tokens(event: dict[str, Any]) -> int:
    if event.get("type") not in {"usage", "tokens", "run"}:
        return 0
    return usage_dict_tokens(event)


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


def expand_input_paths(source: str, inputs: list[str] | None) -> list[Path]:
    patterns = inputs or list(SOURCE_DEFAULTS[source])
    paths: list[Path] = []
    seen: set[Path] = set()
    for raw_pattern in patterns:
        pattern = os.path.expanduser(raw_pattern)
        if any(char in pattern for char in "*?["):
            candidates = [Path(match) for match in glob.glob(pattern, recursive=True)]
        else:
            candidate = Path(pattern)
            if candidate.is_dir():
                candidates = list(candidate.rglob("*.jsonl")) + list(candidate.rglob("*.json"))
            else:
                candidates = [candidate]
        for candidate in sorted(candidates):
            if not candidate.exists() or not candidate.is_file():
                continue
            if candidate.suffix.lower() not in {".jsonl", ".json"}:
                continue
            resolved = candidate.resolve()
            if resolved in seen:
                continue
            seen.add(resolved)
            paths.append(resolved)
    return paths


def json_records_from_value(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if not isinstance(value, dict):
        return []

    records = [value]
    for key in ("events", "messages", "records", "items", "logs"):
        items = value.get(key)
        if isinstance(items, list):
            records.extend(item for item in items if isinstance(item, dict))
    return records


def read_log_records(path: Path) -> tuple[list[dict[str, Any]], int]:
    records: list[dict[str, Any]] = []
    errors = 0
    if path.suffix.lower() == ".jsonl":
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except json.JSONDecodeError:
                    errors += 1
                    continue
                if isinstance(record, dict):
                    records.append(record)
        return records, errors

    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            value = json.load(handle)
    except json.JSONDecodeError:
        return records, 1
    records.extend(json_records_from_value(value))
    return records, errors


def content_has_tool_result(content: Any) -> bool:
    if isinstance(content, list):
        return any(isinstance(item, dict) and item.get("type") == "tool_result" for item in content)
    return False


def content_has_human_payload(content: Any) -> bool:
    if isinstance(content, str):
        return bool(content.strip())
    if isinstance(content, list):
        if content_has_tool_result(content):
            return False
        human_types = {"text", "image", "document", "file"}
        return any(isinstance(item, dict) and item.get("type") in human_types for item in content)
    return False


def claude_record_tokens(record: dict[str, Any]) -> int:
    message = record.get("message")
    if not isinstance(message, dict):
        return 0
    usage = message.get("usage")
    if not isinstance(usage, dict):
        return 0
    return usage_dict_tokens(usage)


def codex_record_tokens(record: dict[str, Any]) -> int:
    payload = record.get("payload")
    if not isinstance(payload, dict) or payload.get("type") != "token_count":
        return 0
    info = payload.get("info")
    if not isinstance(info, dict):
        return 0
    usage = info.get("last_token_usage")
    if not isinstance(usage, dict):
        return 0
    return usage_dict_tokens(usage)


def generic_record_tokens(record: dict[str, Any]) -> int:
    explicit: list[int] = []
    direct: list[int] = []

    def walk(value: Any, key: str = "") -> None:
        if not isinstance(value, dict):
            if isinstance(value, list):
                for item in value:
                    walk(item)
            return

        if key in {"usage", "token_usage", "last_token_usage"}:
            tokens = usage_dict_tokens(value)
            if tokens:
                explicit.append(tokens)
        elif key not in {"total_token_usage", "cumulative_token_usage"}:
            tokens = usage_dict_tokens(value)
            if tokens:
                direct.append(tokens)

        for child_key, child_value in value.items():
            if child_key in {"total_token_usage", "cumulative_token_usage"}:
                continue
            walk(child_value, child_key)

    walk(record)
    if explicit:
        return sum(explicit)
    return max(direct, default=0)


def claude_is_user_message(record: dict[str, Any], path: Path | None = None) -> bool:
    if path and "subagents" in path.parts:
        return False
    if record.get("type") != "user":
        return False
    message = record.get("message")
    if not isinstance(message, dict) or message.get("role") != "user":
        return False
    return content_has_human_payload(message.get("content"))


def codex_is_user_message(record: dict[str, Any]) -> bool:
    payload = record.get("payload")
    return (
        record.get("type") == "event_msg"
        and isinstance(payload, dict)
        and payload.get("type") == "user_message"
    )


def generic_is_user_message(record: dict[str, Any]) -> bool:
    if record.get("role") == "user" or record.get("type") == "user":
        if not content_has_tool_result(record.get("content")):
            return True

    message = record.get("message")
    if isinstance(message, dict) and message.get("role") == "user":
        if not content_has_tool_result(message.get("content")):
            return True

    payload = record.get("payload")
    if isinstance(payload, dict):
        if payload.get("type") == "user_message":
            return True
        if payload.get("role") == "user" and payload.get("type") in {None, "message", "user"}:
            return not content_has_tool_result(payload.get("content"))
    return False


def record_tokens(source: str, record: dict[str, Any]) -> int:
    if source == "claude":
        return claude_record_tokens(record)
    if source == "codex":
        return codex_record_tokens(record)
    return generic_record_tokens(record)


def is_user_message(source: str, record: dict[str, Any], path: Path | None = None) -> bool:
    if source == "claude":
        return claude_is_user_message(record, path)
    if source == "codex":
        return codex_is_user_message(record)
    return generic_is_user_message(record)


def import_source(
    source: str,
    paths: list[Path],
    output_log: Path,
    dry_run: bool = False,
    exclude_first_user_message: bool = False,
) -> ImportStats:
    stats = ImportStats(source=source)
    for path in paths:
        records, parse_errors = read_log_records(path)
        stats.files += 1
        stats.records += len(records)
        stats.parse_errors += parse_errors

        file_tokens = 0
        file_token_events = 0
        file_user_messages = 0
        file_interruptions = 0
        seen_first_user_message = False

        for record in records:
            tokens = record_tokens(source, record)
            if tokens:
                file_tokens += tokens
                file_token_events += 1

            if not is_user_message(source, record, path):
                continue

            file_user_messages += 1
            if exclude_first_user_message and not seen_first_user_message:
                seen_first_user_message = True
                continue
            file_interruptions += 1

        stats.tokens += file_tokens
        stats.token_events += file_token_events
        stats.user_messages += file_user_messages
        stats.interruptions += file_interruptions

        if dry_run:
            continue

        common = {
            "source": f"{source}-import",
            "imported_from": str(path),
            "records": len(records),
        }
        if file_tokens:
            append_event(output_log, {"type": "usage", "tokens": file_tokens, "token_events": file_token_events, **common})
        if file_interruptions:
            append_event(
                output_log,
                {
                    "type": "interruption",
                    "reason": "user-message",
                    "count": file_interruptions,
                    "user_messages": file_user_messages,
                    "interruption_policy": "exclude-first-user-message-per-file"
                    if exclude_first_user_message
                    else "all-user-messages",
                    **common,
                },
            )

    return stats


def print_import_summary(stats: ImportStats, output_log: Path, dry_run: bool) -> None:
    mode = "dry run" if dry_run else f"wrote {output_log}"
    print(f"IPB import: {stats.source} ({mode})")
    print(f"files: {stats.files:,}")
    print(f"records: {stats.records:,}")
    print(f"token events: {stats.token_events:,}")
    print(f"tokens: {stats.tokens:,}")
    print(f"user messages: {stats.user_messages:,}")
    print(f"imported interruptions: {stats.interruptions:g}")
    if stats.parse_errors:
        print(f"parse errors skipped: {stats.parse_errors:,}")


def add_import_parser(sub: argparse._SubParsersAction[argparse.ArgumentParser], source: str, help_text: str) -> None:
    command = sub.add_parser(f"import-{source}", help=help_text)
    command.add_argument("--path", action="append", default=None, help="Log file, directory, or glob; repeatable.")
    command.add_argument("--out-log", type=Path, default=None, help="Output IPB JSONL path. Defaults to .ipb/events.jsonl.")
    command.add_argument("--dry-run", action="store_true", help="Scan and summarize without writing IPB events.")
    command.add_argument(
        "--exclude-first-user-message",
        action="store_true",
        help="Do not count the first user message in each log file as an interruption.",
    )
    command.add_argument(
        "--include-first-user-message",
        action="store_true",
        help=argparse.SUPPRESS,
    )


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
    report.add_argument("--log", dest="report_log", action="append", type=Path, default=None, help="JSONL event log path; repeatable.")
    report.add_argument("--json", action="store_true", help="Emit machine-readable JSON.")

    classify_cmd = sub.add_parser("classify", help="Classify a raw IPB value.")
    classify_cmd.add_argument("ipb", type=float)
    classify_cmd.add_argument("--json", action="store_true")

    add_import_parser(sub, "claude", "Import historical Claude Code JSONL usage and user messages.")
    add_import_parser(sub, "codex", "Import historical Codex CLI JSONL usage and user messages.")
    add_import_parser(sub, "hermes", "Import Hermes-style JSONL/JSON usage and user messages.")

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
        report_logs = args.report_log or logs
        result = summarize(read_events(report_logs))
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

    if args.command in {"import-claude", "import-codex", "import-hermes"}:
        source = args.command.removeprefix("import-")
        paths = expand_input_paths(source, args.path)
        output_log = args.out_log or primary_log
        stats = import_source(
            source=source,
            paths=paths,
            output_log=output_log,
            dry_run=args.dry_run,
            exclude_first_user_message=args.exclude_first_user_message,
        )
        print_import_summary(stats, output_log, args.dry_run)
        return 0

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
