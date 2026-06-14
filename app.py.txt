import os
from flask import Flask, request, jsonify
from slack_sdk import WebClient

app = Flask(__name__)

# Initialize Slack Client
slack_client = WebClient(token=os.environ.get("SLACK_BOT_TOKEN"))

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_URL = "https://openrouter.ai"

@app.route("/slack/events", methods=["POST"])
def slack_events():
    data = request.json
    
    # URL Verification for Slack challenge
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})
    
    # Handle incoming messages
    if "event" in data:
        event = data["event"]
        
        # Ignore messages sent by the bot itself to prevent infinite loops
        if event.get("bot_id") is None and "text" in event:
            user_text = event["text"]
            channel_id = event["channel"]
            
            # Send payload to OpenRouter
            import requests
            headers = {
                "Authorization": f"Bearer {OPENROUTER_API_KEY}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": "meta-llama/llama-3-70b-instruct", # Replace with your chosen model
                "messages": [{"role": "user", "content": user_text}]
            }
            
            response = requests.post(OPENROUTER_URL, headers=headers, json=payload)
            ai_response = response.json()["choices"][0]["message"]["content"]
            
            # Post the AI response back to Slack
            slack_client.chat_postMessage(channel=channel_id, text=ai_response)
            
    return jsonify({"status": "ok"})

if __name__ == "__main__":
    app.run(port=3000)
