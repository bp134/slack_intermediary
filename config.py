import os

DATA_PATH = os.environ.get("DATA_PATH", "/data")
MEMORY_ROOT = os.path.join(DATA_PATH, "memory")
MAP_FILE = os.path.join(DATA_PATH, "id_map.json")
MASTER_CSV = os.path.join(DATA_PATH, "master_tasks.csv")
LOG_FILE = os.path.join(DATA_PATH, "bot_activity.log")
PAUSE_FILE = os.path.join(DATA_PATH, "bot_paused")

RETENTION_DAYS = int(os.environ.get("MEMORY_RETENTION_DAYS", "7"))

TASK_KEYWORDS = (
    "owing",
    "follow up",
    "follow-up",
    "action",
    "remind",
    "deadline",
    "urgent",
    "outstanding",
    "need to",
    "needs to",
    "must",
)

PSEUDONYMIZE_ENTITIES = (
    "PERSON",
    "PHONE_NUMBER",
    "EMAIL_ADDRESS",
    "LOCATION",
    "DATE_TIME",
)
