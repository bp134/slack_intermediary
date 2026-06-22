import logging
import os

from config import DATA_PATH, LOG_FILE, MAP_FILE, MASTER_CSV, MEMORY_ROOT
from memory import init_db, purge_old_memory
from storage import atomic_write_json


def setup_logging() -> None:
    logging.basicConfig(
        filename=LOG_FILE,
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )
    if os.path.exists(LOG_FILE):
        os.chmod(LOG_FILE, 0o600)


def initialize_storage() -> bool:
    if not os.path.exists(DATA_PATH):
        logging.error("Persistent disk not found at %s.", DATA_PATH)
        return False

    os.makedirs(MEMORY_ROOT, exist_ok=True)

    if not os.path.exists(MAP_FILE):
        atomic_write_json(MAP_FILE, {})
    if not os.path.exists(MASTER_CSV):
        with open(MASTER_CSV, "w", encoding="utf-8") as f:
            f.write("Date,Task,Patient_ID,Staff_Assigned,Status\n")

    for path in (MAP_FILE, MASTER_CSV):
        os.chmod(path, 0o600)

    init_db()
    setup_logging()
    purge_old_memory()
    return True
