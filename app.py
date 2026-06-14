import os
import sqlite3
import requests
from flask import Flask, request, jsonify
from slack_sdk import WebClient

app = Flask(__name__)

# Initialize Slack Client
slack_client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openrouter/auto")
DB_FILE = "history.db"

def init_db():
    """Creates the history table if it does not exist."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id TEXT,
                role TEXT,
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def save_message(channel_id, role, content):
    """Saves a user or assistant message to the database."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (channel_id, role, content) VALUES (?, ?, ?)",
            (channel_id, role, content)
        )
        conn.commit()

def get_history(channel_id, limit=10):
    """Retrieves the recent chat history for a specific Slack channel."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        # Fetch latest messages first, then reverse them to chronological order
        cursor.execute(
            "SELECT role, content FROM messages WHERE channel_id = ? ORDER BY id DESC LIMIT ?",
            (channel_id, limit)
        )
        rows = cursor.fetchall()
        return [{"role": r, "content": c} for r, c in reversed(rows)]


def get_openrouter_reply(messages):
    """Returns a chat completion response from OpenRouter."""
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
    }

    response = requests.post(
        OPENROUTER_API_URL,
        headers=headers,
        json=payload,
        timeout=30,
    )

    try:
        response_data = response.json()
    except ValueError as exc:
        preview = response.text[:200].strip()
        raise RuntimeError(
            f"OpenRouter returned a non-JSON response "
            f"(HTTP {response.status_code}): {preview or '<empty body>'}"
        ) from exc

    if not response.ok:
        error = response_data.get("error")
        if isinstance(error, dict):
            message = error.get("message")
        else:
            message = error
        message = message or response.text
        raise RuntimeError(
            f"OpenRouter request failed with HTTP {response.status_code}: {message}"
        )

    try:
        return response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected OpenRouter response: {response_data}") from exc

# Initialize database on startup
init_db()

@app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.json
    
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})
    
    if "event" in data:
        event = data["event"]
        
        if event.get("bot_id") is None and "text" in event:
            user_text = event["text"]
            channel_id = event["channel"]
            
            # 1. Save the incoming user message to memory
            save_message(channel_id, "user", user_text)
            
            # 2. Retrieve the last 10 messages for this specific channel
            history = get_history(channel_id, limit=10)
            
            # 3. Call OpenRouter with the full conversation history
            try:
                ai_response = get_openrouter_reply(history)
                
                # 4. Save the bot's own response to memory
                save_message(channel_id, "assistant", ai_response)
                
            except Exception as e:
                ai_response = f"Sorry, I encountered an error calling OpenRouter: {str(e)}"
            
            slack_client.chat_postMessage(channel=channel_id, text=ai_response)
            
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
