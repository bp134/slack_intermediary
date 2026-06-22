# Neena — Belfield Pharmacy Slack bot

Channel-scoped, pseudonymized task memory for Slack.

## Setup

```bash
cd slack_intermediary
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
python -m spacy download en_core_web_lg   # required by Presidio
cp .env.example .env
# Edit .env with Slack tokens, OpenRouter key, and user IDs
```

For local dev without `/data`:

```bash
set DATA_PATH=./data
python app.py
```

## Policy docs

| File | Purpose |
|------|---------|
| `Memory.md` | Memory and privacy rules for the LLM |
| `Hard Limits.md` | Non-negotiable boundaries |
| `AI_AGENT.md` | Daily workflow |
| `SOUL.md` | Agent identity |
| `USER.md` | Owner context |
| `HEARTBEAT.md` | Active monitoring reminders |
| `#Memory AI Agent/` | Constitution and operational boundaries |

## Run

```bash
python app.py
```

Requires Socket Mode: `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `MY_SLACK_USER_ID`, and `OPENROUTER_API_KEY`.

Slack bot scopes: `chat:write`, `channels:history`, `groups:history`, `im:history`, `im:write`, `users:read`.
