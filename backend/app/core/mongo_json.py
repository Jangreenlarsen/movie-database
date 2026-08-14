"""Round-trippable JSON encoding for raw MongoDB documents — shared by the
library export/import (feature #60) and the full system backup/restore
(feature #61). Uses a small subset of MongoDB's own Extended JSON
convention (`{"$oid": ...}` / `{"$date": ...}` / `{"$binary": ...}`)
instead of a heuristic "does this string look like a date" guess, so
encoding is unambiguous.

`{"$binary": ...}` (base64) was added for feature #153's `poster_cache`
collection, which stores raw cached image bytes as BSON `Binary` —
otherwise indistinguishable from plain `bytes`, which FastAPI/Pydantic
can't serialize to JSON at all."""

import base64
from datetime import datetime

from bson import Binary, ObjectId


def to_json_safe(value):
    if isinstance(value, ObjectId):
        return {"$oid": str(value)}
    if isinstance(value, datetime):
        return {"$date": value.isoformat()}
    if isinstance(value, (Binary, bytes)):
        return {"$binary": base64.b64encode(bytes(value)).decode("ascii")}
    if isinstance(value, list):
        return [to_json_safe(v) for v in value]
    if isinstance(value, dict):
        return {key: to_json_safe(v) for key, v in value.items()}
    return value


def from_json_safe(value):
    if isinstance(value, dict):
        if value.keys() == {"$oid"}:
            return ObjectId(value["$oid"])
        if value.keys() == {"$date"}:
            return datetime.fromisoformat(value["$date"])
        if value.keys() == {"$binary"}:
            return Binary(base64.b64decode(value["$binary"]))
        return {key: from_json_safe(v) for key, v in value.items()}
    if isinstance(value, list):
        return [from_json_safe(v) for v in value]
    return value
