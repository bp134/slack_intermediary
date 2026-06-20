import os
import json
import pandas as pd
from presidio_analyzer import AnalyzerEngine
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig

# Load Engines
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()
MAP_FILE = "/data/id_map.json"
MASTER_CSV = "/data/master_tasks.csv"

def get_or_create_pseudo_id(name):
    if os.path.exists(MAP_FILE):
        with open(MAP_FILE, 'r') as f:
            mapping = json.load(f)
    else:
        mapping = {}
    if name in mapping:
        return mapping[name]
    new_id = f"PATIENT_{len(mapping) + 1000}"
    mapping[name] = new_id
    with open(MAP_FILE, 'w') as f:
        json.dump(mapping, f)
    return new_id

def pseudonymize_text(text):
    results = analyzer.analyze(text=text, entities=["PERSON"], language='en')
    detected_names = [res.text for res in results]
    for name in detected_names:
        pid = get_or_create_pseudo_id(name)
        text = text.replace(name, pid)
    return text

def translate_tasks_to_real_names(text):
    if not os.path.exists(MAP_FILE): return text
    with open(MAP_FILE, 'r') as f:
        mapping = json.load(f)
    reverse_map = {v: k for k, v in mapping.items()}
    for pid, name in reverse_map.items():
        text = text.replace(pid, name)
    return text