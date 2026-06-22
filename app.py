import logging
import os

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from access import can_view_master_list, is_admin, validate_env
from init_data import initialize_storage
from logic import prepare_task_summary, pseudonymize_text, translate_tasks_to_real_names
from memory import (
    add_task,
    get_history,
    is_paused,
    looks_like_task,
    mark_latest_open_task_done,
    read_master_csv,
    save_message,
    set_paused,
)
from openrouter import get_openrouter_reply

logger = logging.getLogger(__name__)

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))


def _is_completion_message(text: str) -> bool:
    lower = text.lower().strip()
    return lower.startswith("done") or lower.startswith("completed")


def _reply_with_openrouter(channel: str, pseudo_text: str, client) -> None:
    save_message(channel, "user", pseudo_text)
    history = get_history(channel, limit=10)

    try:
        ai_response = get_openrouter_reply(history)
        save_message(channel, "assistant", ai_response)
        reply_text = translate_tasks_to_real_names(ai_response)
    except Exception as exc:
        logger.error("OpenRouter error: %s", exc)
        reply_text = f"Sorry, I encountered an error calling OpenRouter: {exc}"

    client.chat_postMessage(channel=channel, text=reply_text)


@app.event("message")
def handle_msg(event, client):
    if event.get("subtype") == "bot_message" or "bot_id" in event:
        return

    user = event.get("user")
    channel = event.get("channel")
    text = event.get("text", "")
    ts = event.get("ts", "")

    if not channel or not user:
        return

    lower = text.lower()
    pseudo_text = pseudonymize_text(text)
    logger.info("action=message_received channel=%s user=%s text=%s", channel, user, pseudo_text)

    if is_admin(user) and "emergency stop" in lower:
        set_paused(True)
        logger.critical("action=bot_paused user=%s", user)
        client.chat_postMessage(
            channel=channel,
            text="Bot paused. Admin can send `resume bot` to continue.",
        )
        return

    if is_admin(user) and "resume bot" in lower:
        set_paused(False)
        logger.info("action=bot_resumed user=%s", user)
        client.chat_postMessage(channel=channel, text="Bot resumed.")
        return

    if is_paused():
        return

    if lower.strip() == "show master list":
        if not can_view_master_list(user):
            client.chat_postMessage(
                channel=channel,
                text="You are not authorised to view the master list.",
            )
            logger.warning("action=master_list_denied user=%s", user)
            return
        client.chat_postMessage(channel=user, text=f"```\n{read_master_csv()}\n```")
        logger.info("action=master_list_sent user=%s", user)
        return

    if _is_completion_message(text):
        task_id = mark_latest_open_task_done(channel)
        if task_id:
            client.chat_postMessage(
                channel=channel,
                text=f"Marked task {task_id} as done.",
            )
        return

    if looks_like_task(text):
        summary, patient_ref, urgency = prepare_task_summary(text)
        task_id = add_task(
            channel_id=channel,
            staff_user_id=user,
            summary=summary,
            source_ts=ts,
            patient_ref=patient_ref,
            urgency=urgency,
        )
        logger.info(
            "action=message_processed channel=%s user=%s task=%s",
            channel,
            user,
            task_id,
        )
        return

    _reply_with_openrouter(channel, pseudo_text, client)


if __name__ == "__main__":
    missing = validate_env()
    if missing:
        raise SystemExit(f"Missing required environment variables: {', '.join(missing)}")

    if not initialize_storage():
        raise SystemExit("Storage init failed.")

    logger.info("action=bot_started")
    SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN")).start()
