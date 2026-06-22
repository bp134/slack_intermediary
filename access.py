import logging
import os

logger = logging.getLogger(__name__)


def get_admin_user_id() -> str | None:
    return os.environ.get("MY_SLACK_USER_ID")


def get_authorized_user_ids() -> set[str]:
    raw = os.environ.get("AUTHORIZED_USER_IDS", "")
    ids = {part.strip() for part in raw.split(",") if part.strip()}
    admin = get_admin_user_id()
    if admin:
        ids.add(admin)
    return ids


def is_admin(user_id: str | None) -> bool:
    if not user_id:
        return False
    admin = get_admin_user_id()
    return bool(admin and user_id == admin)


def _is_workspace_member(client, user_id: str) -> bool:
    try:
        result = client.users_info(user=user_id)
        user = result["user"]
    except Exception as exc:
        logger.warning("action=users_info_failed user=%s error=%s", user_id, exc)
        return False

    if user.get("is_bot") or user.get("deleted"):
        return False
    if user.get("is_restricted") or user.get("is_ultra_restricted"):
        return False
    return True


def can_view_master_list(user_id: str | None, client=None) -> bool:
    if not user_id:
        return False

    access_mode = os.environ.get("MASTER_LIST_ACCESS", "workspace").lower()
    if access_mode == "restricted":
        return user_id in get_authorized_user_ids()

    if client is None:
        return True

    return _is_workspace_member(client, user_id)


def llm_enabled() -> bool:
    return os.environ.get("LLM_ENABLED", "false").lower() in ("1", "true", "yes")


def validate_env() -> list[str]:
    missing = []
    for key in ("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN"):
        if not os.environ.get(key):
            missing.append(key)
    if not get_admin_user_id():
        missing.append("MY_SLACK_USER_ID")
    if llm_enabled() and not os.environ.get("OPENROUTER_API_KEY"):
        missing.append("OPENROUTER_API_KEY")
    return missing
