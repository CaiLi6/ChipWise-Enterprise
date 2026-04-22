"""Golden QA dataset storage — JSONL append with in-place update/delete."""

from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

GOLDEN_FILE = Path("data/golden_qa.jsonl")

_write_lock = threading.Lock()


@dataclass
class GoldenQA:
    id: str = field(default_factory=lambda: "g" + uuid.uuid4().hex[:8])
    question: str = ""
    ground_truth_answer: str = ""
    ground_truth_contexts: list[str] = field(default_factory=list)
    chip_ids: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    created_by: str = ""
    created_at: float = field(default_factory=time.time)

    def to_json(self) -> dict[str, Any]:
        return asdict(self)


def _ensure() -> None:
    GOLDEN_FILE.parent.mkdir(parents=True, exist_ok=True)


def list_golden() -> list[dict[str, Any]]:
    if not GOLDEN_FILE.exists():
        return []
    out: list[dict[str, Any]] = []
    with GOLDEN_FILE.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def get_golden(gid: str) -> dict[str, Any] | None:
    for g in list_golden():
        if g.get("id") == gid:
            return g
    return None


def add_golden(rec: GoldenQA) -> GoldenQA:
    _ensure()
    with _write_lock, GOLDEN_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec.to_json(), ensure_ascii=False) + "\n")
    return rec


def delete_golden(gid: str) -> bool:
    if not GOLDEN_FILE.exists():
        return False
    rows = [g for g in list_golden() if g.get("id") != gid]
    with _write_lock:
        tmp = GOLDEN_FILE.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        tmp.replace(GOLDEN_FILE)
    return True


def update_golden(gid: str, updates: dict[str, Any]) -> dict[str, Any] | None:
    rows = list_golden()
    updated: dict[str, Any] | None = None
    for r in rows:
        if r.get("id") == gid:
            r.update(updates)
            updated = r
    if updated is None:
        return None
    with _write_lock:
        tmp = GOLDEN_FILE.with_suffix(".jsonl.tmp")
        with tmp.open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        tmp.replace(GOLDEN_FILE)
    return updated
