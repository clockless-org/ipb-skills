# IPB Skills

`ipb-skills` contains a Codex skill for measuring **IPB: Interruptions Per Billion Tokens**.

IPB is a rough maturity metric for AI-native systems:

```text
IPB = human interruptions / (tokens / 1,000,000,000)
```

Lower IPB means the system can run further before it has to pull a human back into the loop.

## One-Command Install

For Codex users:

```bash
curl -fsSL https://raw.githubusercontent.com/clockless-org/ipb-skills/main/install.sh | bash
```

Then restart Codex and invoke:

```text
Use $ipb to calculate IPB for this project.
```

Manual install through the bundled skill installer:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/.system/skill-installer/scripts/install-skill-from-github.py" \
  --repo clockless-org/ipb-skills \
  --path skills/ipb
```

## Quick Use

After install:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/ipb/scripts/ipb.py" log-usage --tokens 25000000
python3 "${CODEX_HOME:-$HOME/.codex}/skills/ipb/scripts/ipb.py" log-interruption --reason context-needed
python3 "${CODEX_HOME:-$HOME/.codex}/skills/ipb/scripts/ipb.py" report
```

By default it writes `.ipb/events.jsonl` in the current project.

## Import Historical Agent Logs

Dry-run local history first:

```bash
python3 "${CODEX_HOME:-$HOME/.codex}/skills/ipb/scripts/ipb.py" import-claude --dry-run
python3 "${CODEX_HOME:-$HOME/.codex}/skills/ipb/scripts/ipb.py" import-codex --dry-run
python3 "${CODEX_HOME:-$HOME/.codex}/skills/ipb/scripts/ipb.py" import-hermes --path ~/path/to/hermes/logs --dry-run
```

Then rerun without `--dry-run` to append normalized events to `.ipb/events.jsonl`.

Default sources:

- Claude Code: `~/.claude/projects/**/*.jsonl`
- Codex CLI: `~/.codex/sessions/**/*.jsonl` and `~/.codex/archived_sessions/*.jsonl`
- Hermes-style logs: pass `--path`; common JSONL/JSON `usage`, `last_token_usage`, and `role=user` records are supported.

Historical user messages are used as an interruption proxy. Every human user message is counted by default. Claude `subagents` user messages are treated as internal agent traffic. Use `--exclude-first-user-message` only when you want a conservative estimate that ignores each log file's initial task message.

## Five Levels

| Level | IPB | Maturity |
|---|---:|---|
| L1 | `3000+` | Manual AI operation |
| L2 | `1000-2999` | Skilled tool use |
| L3 | `300-999` | Async delegation |
| L4 | `50-299` | Agentic workflow |
| L5 | `<50` | AI-native system |

`<5 IPB` is marked as `AI factory-like`.

## Repository Layout

```text
skills/ipb/               # installable Codex skill
skills/ipb/scripts/ipb.py # logger and reporter
examples/events.jsonl     # sample event log
tests/test_ipb.py         # stdlib tests
```
