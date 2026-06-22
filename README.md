# Neena — Belfield Pharmacy Slack bot

Channel-scoped, pseudonymized task memory for Slack.

## Setup

```bash
cd slack-bot
python -m venv .venv
.venv\Scripts\activate   # Windows
pip install -r requirements.txt
python -m spacy download en_core_web_lg   # required by Presidio
cp .env.example .env
# Edit .env with Slack tokens and user IDs
```

For local dev without `/data`:

```bash
set DATA_PATH=./data
python app.py
```

## Policy docs

| File | Purpose |
|------|---------|
| `Memory.md` | Memory & privacy rules for the LLM |
| `docs/Hard_Limits.md` | Non-negotiable boundaries |
| `docs/AI_AGENT.md` | Daily workflow |
| `docs/MEMORY_DESIGN.md` | Technical architecture |

## Run

```bash
python app.py
```

Requires Socket Mode: `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `MY_SLACK_USER_ID`.
