import logging
import os
import re

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

from access import can_view_master_list, is_admin, llm_enabled, validate_env
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

HELP_TEXT = (
    "I record tasks when messages mention follow-ups, owings, orders, deadlines, or updates. "
    "Say `done` to complete the latest task in this channel, or `show master list` for the full list."
)


def _normalize_message(text: str) -> str:
    return re.sub(r"<@[^>]+>", "", text).strip()


def _is_completion_message(text: str) -> bool:
    lower = _normalize_message(text).lower()
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


def _safe_pseudonymize(text: str) -> str:
    try:
        return pseudonymize_text(text)
    except Exception as exc:
        logger.error("action=pseudonymize_failed error=%s", exc)
        return text


@app.event("message")
def handle_msg(event, client):
    try:
        _handle_msg(event, client)
    except Exception as exc:
        logger.exception("action=handler_failed error=%s", exc)
        channel = event.get("channel")
        if channel:
            client.chat_postMessage(
                channel=channel,
                text="Sorry, something went wrong processing that message. Please try again.",
            )


def _handle_msg(event, client):
    if event.get("subtype") == "bot_message" or "bot_id" in event:
        return

    user = event.get("user")
    channel = event.get("channel")
    text = event.get("text", "")
    ts = event.get("ts", "")

    if not channel or not user:
        return

    normalized = _normalize_message(text)
    lower = normalized.lower()

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
        logger.info("action=message_skipped_paused channel=%s user=%s", channel, user)
        return

    if lower.strip() == "show master list":
        if not can_view_master_list(user, client):
            client.chat_postMessage(
                channel=channel,
                text="The master list is only available to full workspace members.",
            )
            logger.warning("action=master_list_denied user=%s", user)
            return
        master_list = translate_tasks_to_real_names(read_master_csv())
        client.chat_postMessage(channel=user, text=f"```\n{master_list}\n```")
        logger.info("action=master_list_sent user=%s", user)
        return

    if lower.strip() in ("help", "neena help"):
        client.chat_postMessage(channel=channel, text=HELP_TEXT)
        return

    if _is_completion_message(text):
        task_id = mark_latest_open_task_done(channel)
        if task_id:
            client.chat_postMessage(
                channel=channel,
                text=f"Marked task {task_id} as done.",
            )
        else:
            client.chat_postMessage(
                channel=channel,
                text="No open task found in this channel to mark as done.",
            )
        return

    if looks_like_task(normalized):
        pseudo_text = _safe_pseudonymize(text)
        logger.info("action=message_received channel=%s user=%s text=%s", channel, user, pseudo_text)
        summary, patient_ref, urgency = prepare_task_summary(text)
        task_id = add_task(
            channel_id=channel,
            staff_user_id=user,
            summary=summary,
            source_ts=ts,
            patient_ref=patient_ref,
            urgency=urgency,
        )
        display_summary = translate_tasks_to_real_names(summary)
        client.chat_postMessage(
            channel=channel,
            text=f"Recorded task `{task_id}` ({urgency} priority): {display_summary}",
        )
        logger.info(
            "action=message_processed channel=%s user=%s task=%s",
            channel,
            user,
            task_id,
        )
        return

    if llm_enabled():
        pseudo_text = _safe_pseudonymize(text)
        logger.info("action=message_received channel=%s user=%s text=%s", channel, user, pseudo_text)
        _reply_with_openrouter(channel, pseudo_text, client)
        return

    logger.info("action=message_unrecognized channel=%s user=%s", channel, user)
    client.chat_postMessage(channel=channel, text=HELP_TEXT)


def _configure_startup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler()],
        force=True,
    )


if __name__ == "__main__":
    _configure_startup_logging()

    missing = validate_env()
    if missing:
        logger.error("Missing required environment variables: %s", ", ".join(missing))
        raise SystemExit(1)

    from config import DATA_PATH

    if not initialize_storage():
        logger.error(
            "Storage init failed. DATA_PATH=%s exists=%s",
            DATA_PATH,
            os.path.exists(DATA_PATH),
        )
        raise SystemExit(1)

    logger.info("action=bot_started data_path=%s llm_enabled=%s", DATA_PATH, llm_enabled())
    SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN")).start()
