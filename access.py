import os


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


def can_view_master_list(user_id: str | None) -> bool:
    if not user_id:
        return False
    return user_id in get_authorized_user_ids()


def validate_env() -> list[str]:
    missing = []
    for key in ("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN"):
        if not os.environ.get(key):
            missing.append(key)
    if not get_admin_user_id():
        missing.append("MY_SLACK_USER_ID")
    return missing
