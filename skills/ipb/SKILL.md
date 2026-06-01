---
name: ipb
description: Measure Interruptions Per Billion Tokens (IPB) for AI-native workflows and classify automation maturity. Use when Codex needs to log token usage, log human interruptions, import historical token usage or user-message counts from Claude Code, Codex CLI, or Hermes-style JSONL logs, compute IPB, explain what counts as an interruption, or categorize a team/system into the five IPB maturity levels.
---

# IPB

IPB means **Interruptions Per Billion Tokens**:

```text
IPB = interruptions / (tokens / 1,000,000,000)
```

Use IPB to evaluate AI-native system maturity. Token burn shows activity; IPB shows how often the system has to stop and pull humans back into the loop.

## Quick Start

Use the bundled script for deterministic logging and reporting:

```bash
python3 skills/ipb/scripts/ipb.py log-usage --tokens 25000000 --provider openai --model gpt-5
python3 skills/ipb/scripts/ipb.py log-interruption --reason context-needed --note "Needed product decision"
python3 skills/ipb/scripts/ipb.py report
```

When the skill is installed, the script is usually at:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/ipb/scripts/ipb.py" report
```

Default log path is `.ipb/events.jsonl` in the current project. Use `--log <path>` to override.

## Historical Imports

The script can import past token usage and user-message counts from local agent logs:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/ipb/scripts/ipb.py" import-claude --dry-run
python3 "${CODEX_HOME:-$HOME/.codex}/skills/ipb/scripts/ipb.py" import-codex --dry-run
python3 "${CODEX_HOME:-$HOME/.codex}/skills/ipb/scripts/ipb.py" import-hermes --path ~/path/to/hermes/logs --dry-run
```

If the dry run looks right, rerun without `--dry-run` to append normalized events to `.ipb/events.jsonl`, then run:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/ipb/scripts/ipb.py" report
```

Default sources:

- Claude Code: `~/.claude/projects/**/*.jsonl`
- Codex CLI: `~/.codex/sessions/**/*.jsonl` and `~/.codex/archived_sessions/*.jsonl`
- Hermes-style logs: pass `--path`; the importer accepts JSONL/JSON records with common `usage`, `last_token_usage`, and `role=user` shapes.

Historical imports treat human user messages as an interruption proxy. They exclude the first user message in each log file by default because that is usually the initial task definition, not an interruption. Claude `subagents` user messages are treated as internal agent traffic, not human interruptions. Use `--include-first-user-message` when you want raw user-message count as interruptions.

## What Counts

Count an event as an interruption when system execution has to stop for a human during the run:

- Human provides missing context.
- Human approves or chooses the next step before the system can continue.
- Human manually retries, restarts, routes, or repairs an agent/tool flow.
- Human reviews an intermediate artifact and blocks continuation.
- Human changes scope because the system could not resolve ambiguity itself.

Do not count:

- Initial task definition.
- Final acceptance or outcome review.
- Passive dashboard watching.
- Optional async comments that do not block execution.
- Scheduled retrospectives after the run is complete.

## Five Maturity Levels

Lower IPB is better.

| Level | IPB | Maturity |
|---|---:|---|
| L1 | `3000+` | Manual AI operation: humans are still driving the workflow. |
| L2 | `1000-2999` | Skilled tool use: task delegation works, but humans intervene frequently. |
| L3 | `300-999` | Async delegation: batched agent work exists, but review and routing remain heavy. |
| L4 | `50-299` | Agentic workflow: task state, auto retry, and verification reduce interruptions. |
| L5 | `<50` | AI-native system: humans mostly handle goals, boundaries, exceptions, and final judgment. |

If IPB is `<5`, call it **AI factory-like**: humans define goals and compare results; the system runs almost entirely by itself.

## Reporting Workflow

1. Find existing `.ipb/events.jsonl`, LiteLLM logs, provider usage exports, or other usage records.
2. Normalize token records into `usage` events and human blocking points into `interruption` events.
3. Run `ipb.py report --log <path>`.
4. Report total tokens, interruption count, IPB, maturity level, and one practical recommendation to lower IPB.

For the exact event schema, read `references/event-schema.md` when needed.
