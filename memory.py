import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta, timezone

from config import DATA_PATH, MASTER_CSV, MEMORY_ROOT, PAUSE_FILE, RETENTION_DAYS, TASK_KEYWORDS
from storage import atomic_write_json

logger = logging.getLogger(__name__)

DB_FILE = os.path.join(DATA_PATH, "history.db")


def init_db() -> None:
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
    os.chmod(DB_FILE, 0o600)


def save_message(channel_id: str, role: str, content: str) -> None:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO messages (channel_id, role, content) VALUES (?, ?, ?)",
            (channel_id, role, content),
        )
        conn.commit()


def get_history(channel_id: str, limit: int = 10) -> list[dict]:
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT role, content FROM messages WHERE channel_id = ? ORDER BY id DESC LIMIT ?",
            (channel_id, limit),
        )
        rows = cursor.fetchall()
        return [{"role": role, "content": content} for role, content in reversed(rows)]


def is_paused() -> bool:
    return os.path.exists(PAUSE_FILE)


def set_paused(paused: bool) -> None:
    if paused:
        open(PAUSE_FILE, "a", encoding="utf-8").close()
        os.chmod(PAUSE_FILE, 0o600)
    elif os.path.exists(PAUSE_FILE):
        os.unlink(PAUSE_FILE)


def purge_old_memory() -> None:
    if not os.path.isdir(MEMORY_ROOT):
        return
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=RETENTION_DAYS)
    for name in os.listdir(MEMORY_ROOT):
        try:
            day = datetime.strptime(name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if day < cutoff:
            day_path = os.path.join(MEMORY_ROOT, name)
            for filename in os.listdir(day_path):
                os.unlink(os.path.join(day_path, filename))
            os.rmdir(day_path)
            logger.info("Purged memory directory %s", name)


def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def memory_file_path(channel_id: str, date: str | None = None) -> str:
    day = date or _today()
    day_dir = os.path.join(MEMORY_ROOT, day)
    os.makedirs(day_dir, exist_ok=True)
    safe_channel = channel_id.replace("/", "_")
    return os.path.join(day_dir, f"{safe_channel}.json")


def load_channel_memory(channel_id: str, date: str | None = None) -> dict:
    path = memory_file_path(channel_id, date)
    if not os.path.exists(path):
        return {"channel_id": channel_id, "date": date or _today(), "tasks": []}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_channel_memory(channel_id: str, data: dict, date: str | None = None) -> None:
    path = memory_file_path(channel_id, date)
    atomic_write_json(path, data)
    os.chmod(path, 0o600)


def _next_task_id(channel_id: str, date: str) -> str:
    data = load_channel_memory(channel_id, date)
    seq = len(data.get("tasks", [])) + 1
    compact_date = date.replace("-", "")
    return f"T-{compact_date}-{seq:03d}"


def looks_like_task(text: str) -> bool:
    lower = text.lower()
    return any(keyword in lower for keyword in TASK_KEYWORDS)


def add_task(
    channel_id: str,
    staff_user_id: str,
    summary: str,
    source_ts: str,
    patient_ref: str | None = None,
    urgency: str = "medium",
    deadline: str | None = None,
) -> str:
    date = _today()
    data = load_channel_memory(channel_id, date)
    task_id = _next_task_id(channel_id, date)
    task = {
        "id": task_id,
        "summary": summary[:500],
        "patient_ref": patient_ref,
        "staff_user_id": staff_user_id,
        "urgency": urgency,
        "deadline": deadline,
        "status": "open",
        "source_ts": source_ts,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    data.setdefault("tasks", []).append(task)
    save_channel_memory(channel_id, data, date)
    append_master_csv(task, date)
    logger.info(
        "action=task_created channel=%s user=%s task=%s",
        channel_id,
        staff_user_id,
        task_id,
    )
    return task_id


def append_master_csv(task: dict, date: str) -> None:
    patient = task.get("patient_ref") or ""
    line = (
        f"{date},{_csv_escape(task['summary'])},{patient},"
        f"{task.get('staff_user_id', '')},{task.get('status', 'open')}\n"
    )
    with open(MASTER_CSV, "a", encoding="utf-8") as f:
        f.write(line)


def _csv_escape(value: str) -> str:
    if any(ch in value for ch in (",", '"', "\n")):
        return '"' + value.replace('"', '""') + '"'
    return value


def mark_latest_open_task_done(channel_id: str) -> str | None:
    """Mark the most recent open task in this channel (today first, then earlier days)."""
    if not os.path.isdir(MEMORY_ROOT):
        return None

    dates = sorted(
        (name for name in os.listdir(MEMORY_ROOT) if _is_valid_date(name)),
        reverse=True,
    )
    for date in dates:
        data = load_channel_memory(channel_id, date)
        tasks = data.get("tasks", [])
        for task in reversed(tasks):
            if task.get("status") == "open":
                task["status"] = "done"
                save_channel_memory(channel_id, data, date)
                logger.info(
                    "action=task_done channel=%s task=%s",
                    channel_id,
                    task.get("id"),
                )
                return task.get("id")
    return None


def _is_valid_date(name: str) -> bool:
    try:
        datetime.strptime(name, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def list_open_tasks(channel_id: str, days: int | None = None) -> list[dict]:
    days = days or RETENTION_DAYS
    cutoff = datetime.now(timezone.utc).date() - timedelta(days=days)
    open_tasks: list[dict] = []
    if not os.path.isdir(MEMORY_ROOT):
        return open_tasks
    for name in sorted(os.listdir(MEMORY_ROOT)):
        try:
            day = datetime.strptime(name, "%Y-%m-%d").date()
        except ValueError:
            continue
        if day < cutoff:
            continue
        data = load_channel_memory(channel_id, name)
        for task in data.get("tasks", []):
            if task.get("status") == "open":
                open_tasks.append(task)
    return open_tasks


def read_master_csv() -> str:
    if not os.path.exists(MASTER_CSV):
        return "Date,Task,Patient_ID,Staff_Assigned,Status\n"
    with open(MASTER_CSV, encoding="utf-8") as f:
        return f.read()
