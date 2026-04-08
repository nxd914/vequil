# 🔍 Vequil — AI Agent Ledger

<p align="center">
  <strong>Observe every agent action in one place.</strong>
</p>

<p align="center">
  <a href="https://github.com/nxd914/vequil"><img src="https://img.shields.io/github/stars/nxd914/vequil?style=for-the-badge" alt="Stars"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" alt="MIT License"></a>
</p>

Vequil is an open-source ledger for AI agent activity. Connect any runtime and Vequil records actions, tool calls, cost, and anomalies in a single dashboard and ingest API.

[Dashboard](web/static/dashboard.html) · [OpenClaw Plugin](misc/openclaw/README_OPENCLAW.md) · [Ingest API](#multi-tenant-ingestion)

## Quick Start

Runtime: **Python 3.10+**

```bash
git clone https://github.com/nxd914/vequil.git
cd vequil

pip install -r requirements.txt

PYTHONPATH=src uvicorn vequil.asgi:app --reload
```

Then open `http://127.0.0.1:8000/dashboard.html` in your browser.

## OpenClaw Integration

Connect your OpenClaw agent to Vequil in under 60 seconds.

```bash
# 1. Copy the plugin into your OpenClaw workspace
cp misc/openclaw/vequil_plugin.py ~/.openclaw/workspace/skills/vequil/

# 2. Set your Vequil endpoint
export VEQUIL_ENDPOINT=http://localhost:8000/api/log

# 3. That's it — every tool_result_persist event now logs to Vequil
```

Full guide: [README_OPENCLAW.md](misc/openclaw/README_OPENCLAW.md)

## Production toggles

Environment variables used by the server:

- `DASHBOARD_API_KEY`: API key required for private API access.
- `VEQUIL_REQUIRE_AUTH`: defaults to `1` (auth required). Set `0` only for local demos.
- `VEQUIL_PUBLIC_RATE_LIMIT`: per-IP per-minute limit for public endpoints (default `60`).
- `VEQUIL_CORS_ALLOW_ORIGIN`: CORS allow origin (default `*`).

## Multi-tenant ingestion (beta)

Vequil now supports workspace-scoped ingest keys and a stable `/api/ingest` schema.

1) Create a workspace (admin key protected):

```bash
curl -sS -X POST "http://localhost:8000/api/workspaces" \
  -H "X-API-Key: $DASHBOARD_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"name":"Context Operator","slug":"contextoperator"}'
```

2) Use the returned `ingest_api_key` in `X-Workspace-Key`:

```bash
curl -sS -X POST "http://localhost:8000/api/ingest" \
  -H "X-Workspace-Key: vk_ws_..." \
  -H "Content-Type: application/json" \
  -d '{
    "source":"openclaw",
    "event_type":"tool_call",
    "event_status":"success",
    "event_at":"2026-04-08T01:30:00Z",
    "agent_id":"ops-agent-1",
    "session_id":"session-123",
    "tool_name":"bash",
    "cost_usd":0.012,
    "metadata":{"action_id":"abc123","project":"vequil"}
  }'
```

Manage workspace ingest keys:

```bash
# list keys
curl -sS -H "X-API-Key: $DASHBOARD_API_KEY" \
  "http://localhost:8000/api/workspaces/1/keys"

# create a new key
curl -sS -X POST -H "X-API-Key: $DASHBOARD_API_KEY" \
  "http://localhost:8000/api/workspaces/1/keys"

# revoke a key
curl -sS -X DELETE -H "X-API-Key: $DASHBOARD_API_KEY" \
  "http://localhost:8000/api/workspaces/1/keys/2"
```

Quick onboarding payload:

```bash
curl -sS -H "X-API-Key: $DASHBOARD_API_KEY" \
  "http://localhost:8000/api/onboarding/quickstart"
```

## What Gets Logged

- Every tool call and result
- Session metadata (agent ID, model, timestamp)
- Anomalies: runaway loops, unauthorized sub-agent spend, orphaned tasks, duplicate execution
- Agent Quality Score — shareable weekly report card

## Integrations

| Runtime | Status |
|---|---|
| OpenClaw | ✅ Live |
| Anthropic API / Claude | ✅ Live |
| OpenAI API | ✅ Live |
| LangChain | ✅ Live |
| Moltbook | ✅ Live |

Vequil is runtime-agnostic. If your agent can POST JSON, it can send activity to `/api/ingest`.
