import os
import json
import logging

DATA_PATH = "/data"
MAP_FILE = os.path.join(DATA_PATH, "id_map.json")
MASTER_CSV = os.path.join(DATA_PATH, "master_tasks.csv")

def initialize_storage():
    if not os.path.exists(DATA_PATH):
        logging.error("Persistent disk not found at /data.")
        return False
    if not os.path.exists(MAP_FILE):
        with open(MAP_FILE, 'w') as f: json.dump({}, f)
    if not os.path.exists(MASTER_CSV):
        with open(MASTER_CSV, 'w') as f: 
            f.write("Date,Task,Patient_ID,Staff_Assigned,Status\n")
    os.chmod(MAP_FILE, 0o600)
    os.chmod(MASTER_CSV, 0o600)
    return True