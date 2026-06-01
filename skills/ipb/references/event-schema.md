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

## Example Report

```text
tokens: 4,200,000,000
interruptions: 840
IPB: 200.00
level: L4 - Agentic workflow
```
