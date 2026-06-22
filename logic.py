import json
import os
import re

from filelock import FileLock
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider

from config import MAP_FILE, PSEUDONYMIZE_ENTITIES, SPACY_MODEL
from storage import atomic_write_json

_analyzer: AnalyzerEngine | None = None


def _get_analyzer() -> AnalyzerEngine:
    global _analyzer
    if _analyzer is None:
        provider = NlpEngineProvider(
            nlp_configuration={
                "nlp_engine_name": "spacy",
                "models": [{"lang_code": "en", "model_name": SPACY_MODEL}],
            }
        )
        _analyzer = AnalyzerEngine(
            nlp_engine=provider.create_engine(),
            supported_languages=["en"],
        )
    return _analyzer


def get_or_create_pseudo_id(name: str) -> str:
    lock = FileLock(MAP_FILE + ".lock")
    with lock:
        if os.path.exists(MAP_FILE):
            with open(MAP_FILE, encoding="utf-8") as f:
                mapping = json.load(f)
        else:
            mapping = {}

        if name in mapping:
            return mapping[name]

        new_id = f"PATIENT_{len(mapping) + 1000}"
        mapping[name] = new_id
        atomic_write_json(MAP_FILE, mapping)
        os.chmod(MAP_FILE, 0o600)
        return new_id


def _extract_patient_ref(text: str) -> str | None:
    match = re.search(r"PATIENT_\d+", text)
    return match.group(0) if match else None


def _infer_urgency(text: str) -> str:
    lower = text.lower()
    if "urgent" in lower or "asap" in lower:
        return "high"
    if "critical" in lower or "emergency" in lower:
        return "critical"
    if "low priority" in lower:
        return "low"
    return "medium"


def pseudonymize_text(text: str) -> str:
    if not text:
        return text

    analyzer = _get_analyzer()
    results = analyzer.analyze(
        text=text,
        entities=list(PSEUDONYMIZE_ENTITIES),
        language="en",
    )

    for res in sorted(results, key=lambda r: r.start, reverse=True):
        span = text[res.start : res.end]
        if res.entity_type == "PERSON":
            replacement = get_or_create_pseudo_id(span)
        else:
            replacement = f"[{res.entity_type}]"
        text = text[: res.start] + replacement + text[res.end :]

    return text


def translate_tasks_to_real_names(text: str) -> str:
    if not os.path.exists(MAP_FILE):
        return text
    with open(MAP_FILE, encoding="utf-8") as f:
        mapping = json.load(f)
    for name, pid in mapping.items():
        text = text.replace(pid, name)
    return text


def prepare_task_summary(raw_text: str) -> tuple[str, str | None, str]:
    summary = pseudonymize_text(raw_text)
    patient_ref = _extract_patient_ref(summary)
    urgency = _infer_urgency(raw_text)
    return summary, patient_ref, urgency
