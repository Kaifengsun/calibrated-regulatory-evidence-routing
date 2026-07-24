"""Content-addressed cache for immutable retrieval and path artifacts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


def _canonical_json(payload: Any) -> bytes:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


@dataclass(frozen=True, slots=True)
class CacheKey:
    domain: str
    corpus_hash: str
    query_hash: str
    protocol_hash: str
    path_id: str
    code_commit: str

    def digest(self) -> str:
        return hashlib.sha256(_canonical_json(self.payload())).hexdigest()

    def payload(self) -> dict[str, str]:
        return {
            "code_commit": self.code_commit,
            "corpus_hash": self.corpus_hash,
            "domain": self.domain,
            "path_id": self.path_id,
            "protocol_hash": self.protocol_hash,
            "query_hash": self.query_hash,
        }


class ResultCache:
    """Store JSON artifacts by a complete immutable experiment key."""

    def __init__(self, root: Path) -> None:
        self.root = root

    def path_for(self, key: CacheKey) -> Path:
        return self.root / key.domain / f"{key.digest()}.json"

    def get(self, key: CacheKey) -> dict[str, Any] | None:
        path = self.path_for(key)
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload.get("cache_key") != key.payload():
            raise RuntimeError(f"cache-key mismatch: {path}")
        value = payload.get("value")
        if not isinstance(value, dict):
            raise RuntimeError(f"invalid cached value: {path}")
        return value

    def put(self, key: CacheKey, value: dict[str, Any]) -> Path:
        path = self.path_for(key)
        payload = {"cache_key": key.payload(), "value": value}
        serialized = _canonical_json(payload) + b"\n"
        if path.exists():
            if path.read_bytes() != serialized:
                raise FileExistsError(f"refusing to overwrite different cache value: {path}")
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_bytes(serialized)
        temporary.replace(path)
        return path
