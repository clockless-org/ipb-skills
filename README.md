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
