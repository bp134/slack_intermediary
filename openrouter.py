import os
import requests

OPENROUTER_API_KEY = os.environ.get("OPENROUTER_API_KEY")
OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = os.environ.get("OPENROUTER_MODEL", "openrouter/auto")

MEMORY_DIR = os.path.join(os.path.dirname(__file__), "#Memory AI Agent")
CONSTITUTION_FILES = [
    "AI Agent Constitution and Context.md",
    "AI Agent Constitution and Boundaries.md",
]


def load_system_prompt():
    sections = []
    for filename in CONSTITUTION_FILES:
        path = os.path.join(MEMORY_DIR, filename)
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                sections.append(f.read().strip())
    if not sections:
        return (
            "You are the Belfield Pharmacy Project Manager. "
            "Monitor Slack for tasks and deadlines. Keep responses professional and work-focused."
        )
    return "\n\n---\n\n".join(sections)


def get_openrouter_reply(messages):
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [{"role": "system", "content": load_system_prompt()}, *messages],
    }

    response = requests.post(
        OPENROUTER_API_URL,
        headers=headers,
        json=payload,
        timeout=30,
    )

    try:
        response_data = response.json()
    except ValueError as exc:
        preview = response.text[:200].strip()
        raise RuntimeError(
            f"OpenRouter returned a non-JSON response "
            f"(HTTP {response.status_code}): {preview or '<empty body>'}"
        ) from exc

    if not response.ok:
        error = response_data.get("error")
        if isinstance(error, dict):
            message = error.get("message")
        else:
            message = error
        message = message or response.text
        raise RuntimeError(
            f"OpenRouter request failed with HTTP {response.status_code}: {message}"
        )

    try:
        return response_data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"Unexpected OpenRouter response: {response_data}") from exc
