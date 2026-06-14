import os
import sqlite3
import requests
from flask import Flask, request, jsonify
from slack_sdk import WebClient

app = Flask(__name__)

# Initialize Slack Client
slack_client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))
OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
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
            
            # 3. Construct payload with the full conversation history
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": " openrouter/auto"
                "messages": history
            }
            
            try:
                response = requests.post("https://openrouter.ai", headers=headers, json=payload)
                response.raise_for_status()
                ai_response = response.json()["choices"]["message"]["content"]
                
                # 4. Save the bot's own response to memory
                save_message(channel_id, "assistant", ai_response)
                
            except Exception as e:
                ai_response = f"Sorry, I encountered an error retrieving history: {str(e)}"
            
            slack_client.chat_postMessage(channel=channel_id, text=ai_response)
            
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
