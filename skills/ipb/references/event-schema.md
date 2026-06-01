# IPB Event Schema

Use JSONL: one JSON object per line.

## Usage Event

```json
{"type":"usage","tokens":25000000,"provider":"openai","model":"gpt-5","task_id":"task-123"}
```

`tokens` is preferred. If absent, the reporter also accepts `total_tokens`, or sums common fields:

- `input_tokens`
- `output_tokens`
- `cache_read_tokens`
- `cache_write_tokens`
- `reasoning_tokens`

## Interruption Event

```json
{"type":"interruption","reason":"context-needed","task_id":"task-123","note":"Needed pricing decision"}
```

Optional fields:

- `count`: numeric count, default `1`
- `counted`: set to `false` to keep a non-counted note in the log

Recommended reasons:

- `context-needed`
- `approval-needed`
- `manual-retry`
- `routing`
- `human-review-blocked`
- `scope-change`
- `tool-failure`
- `policy-decision`

## Imported Events

Historical import commands append normal `usage` and `interruption` events with import metadata:

```json
{"type":"usage","tokens":25000000,"source":"codex-import","imported_from":"/path/to/session.jsonl","records":1200,"token_events":45}
```

```json
{"type":"interruption","reason":"user-message","count":13,"source":"claude-import","imported_from":"/path/to/session.jsonl","user_messages":13,"interruption_policy":"all-user-messages"}
```

For historical logs, `user-message` interruptions are a proxy. The importer counts every human user message by default and treats Claude `subagents` user messages as internal agent traffic. Use `--exclude-first-user-message` for a conservative estimate that ignores each log file's initial task message.

## Example Report

```text
tokens: 4,200,000,000
interruptions: 840
IPB: 200.00
level: L4 - Agentic workflow
```
