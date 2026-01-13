# Quality SLOs (Phase E2)

This runbook covers the "quality steering" SLO alerts (fast/slow burn) and the Grafana Quality dashboard.

## Fast vs. Slow burn

- **Fast burn**: `WINDOW=10m`, `for=10m` — catches sustained regressions quickly without paging on single spikes.
- **Slow burn**: `WINDOW=2h`, `for=30m` — catches longer, lower-grade degradations.

If traffic is very low, ratios may look noisy. Check traffic first.

## Top queries (copy/paste)

### Traffic (context)

```
sum(rate(ki_ana_chat_answer_duration_seconds_count[5m]))
```

### SLO-1 Latency p95 (intent-aware)

General (target p95 <= 2.0s):

```
histogram_quantile(0.95, sum(rate(ki_ana_chat_answer_duration_seconds_bucket{intent="general"}[10m])) by (le))
```

Tool (target p95 <= 6.0s):

```
histogram_quantile(0.95, sum(rate(ki_ana_chat_answer_duration_seconds_bucket{intent="tool"}[10m])) by (le))
```

Factual/Research (target p95 <= 8.0s):

```
histogram_quantile(0.95, sum(rate(ki_ana_chat_answer_duration_seconds_bucket{intent=~"factual|research"}[10m])) by (le))
```

### SLO-2 Tool error rate

```
sum(rate(ki_ana_chat_tool_calls_total{status="error"}[10m]))
/
clamp_min(sum(rate(ki_ana_chat_tool_calls_total[10m])), 1)
```

### SLO-3 Answers without sources rate (proxy; only factual|research)

```
sum(rate(ki_ana_chat_answers_without_sources_total{intent=~"factual|research"}[10m]))
/
clamp_min(sum(rate(ki_ana_chat_answer_duration_seconds_count{intent=~"factual|research"}[10m])), 1)
```

### SLO-4 Consent prompt rate (anti-spam)

```
sum(rate(ki_ana_learning_consent_total{kind="prompt"}[10m]))
/
clamp_min(sum(rate(ki_ana_chat_answer_duration_seconds_count[10m])), 1)
```

### SLO-5 Negative feedback rate

```
sum(rate(ki_ana_chat_feedback_total{status="negative"}[10m]))
/
clamp_min(sum(rate(ki_ana_chat_feedback_total[10m])), 1)
```

## Triage actions

### Tool errors (SLO-2)

- Check dependency health (`ki_ana_dependency_up{dependency=~"redis|qdrant|minio"}`) and timeouts.
- Check Celery worker health/backlog (`ki_ana_celery_worker_up`, `ki_ana_celery_queue_backlog`).
- Look for upstream rate limits / auth issues in app logs.

### Latency (SLO-1)

- Correlate with traffic and backlog; confirm this is not a low-traffic artifact.
- Check worker backlog and dependency latency (Redis/Qdrant/MinIO).
- Check DB latency and connection pool saturation.

### No-sources proxy (SLO-3)

- Confirm the spike is limited to `intent in {factual,research}`.
- Inspect recent pipeline/routing changes affecting retrieval or source rendering.
- Optional mitigation (if desired later): enforce source-required behavior for these intents.

### Consent prompt spam (SLO-4)

- Identify whether a feature change increased prompts/corrections.
- Add/tune cooldowns and triggers to avoid repeated prompts for the same user/session.

### Negative feedback spike (SLO-5)

- Check recent releases, prompt/policy changes, and routing/intent changes.
- Sample recent conversations (privacy-safe) to identify common failure patterns.

## Dashboard

- Grafana: `KI_ana - Quality`
- JSON source: `monitoring/grafana/dashboards/kiana-quality.json`

## Quality Gates (observational → optional enforcing)

Quality Gates are derived from the same quality signals but are **observational by default**. Enforcement is opt-in via env flags.

### Env Flags

Global switch:

- `QUALITY_GATES_ENABLED=0|1` (default: 0)

Per-gate switches (only applied if global is enabled):

- `QUALITY_GATE_SOURCES_REQUIRED=0|1` (default: 0)
- `QUALITY_GATE_LEARNING_COOLDOWN=0|1` (default: 0)
- `QUALITY_GATE_TOOLS_DISABLED=0|1` (default: 0) *(currently observational-only unless enforced later)*

### Gate behavior (what it does)

- `sources_required`:
	- If enforced and intent is source-expected (e.g. factual/research) but response has 0 sources → replaces final text with a short refusal asking for web/link.
- `learning_cooldown`:
	- If enforced → suppresses style consent prompt to prevent prompt spam.
- `tools_disabled`:
	- Observational-only (for now). Intended enforcement: skip tool calls and answer in no-tool mode.

### How to verify gates are active

Prometheus:

- `sum(increase(ki_ana_quality_gate_total[10m])) by (gate,mode)`

Explain (per answer):

- `explain.gates.active` / `explain.gates.enforced` (if present)

### Quick rollback

Set:

- `QUALITY_GATES_ENABLED=0`

Redeploy backend (and worker if needed). Gates will stop enforcing immediately.
