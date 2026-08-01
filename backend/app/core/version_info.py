import json
from pathlib import Path

_VERSION_FILE = Path(__file__).resolve().parents[3] / "version.json"


def _load() -> dict:
    with _VERSION_FILE.open(encoding="utf-8") as f:
        data = json.load(f)
    return {"version": data["version"], "build": data["build"]}


VERSION_INFO = _load()
