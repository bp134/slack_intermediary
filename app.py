import os
import logging
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from init_data import initialize_storage
from logic import pseudonymize_text

# 1. Configure Logging
logging.basicConfig(
    filename='/data/bot_activity.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))
ADMIN = os.environ.get("MY_SLACK_USER_ID")

@app.event("message")
def handle_msg(event, client):
    # LOOP PROTECTION: Ignore bots
    if event.get("subtype") == "bot_message" or "bot_id" in event: 
        return
    
    user = event.get("user")
    text = event.get("text", "")
    
    # Log the incoming event (Anonymized)
    clean_text = pseudonymize_text(text)
    logging.info(f"User {user} sent: {clean_text}")
    
    # EMERGENCY STOP
    if "emergency stop" in text.lower() and user == ADMIN:
        logging.critical("Emergency stop initiated by admin.")
        client.chat_postMessage(channel=event['channel'], text="Emergency stop activated. Shutting down.")
        os._exit(1)
        
    # ... Rest of your processing logic ...

if __name__ == "__main__":
    if initialize_storage():
        logging.info("Agent starting successfully.")
        SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN")).start()
    else:
        logging.error("Agent failed to start: Storage init failed.")