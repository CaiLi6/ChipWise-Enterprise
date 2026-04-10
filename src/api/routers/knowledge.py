"""Knowledge Notes CRUD API (§5C1)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

router = APIRouter(prefix="/api/v1/knowledge", tags=["knowledge"])


class KnowledgeNoteCreate(BaseModel):
    chip_id: int | None = None
    content: str
    note_type: str = "comment"  # tag|comment|design_tip|errata_link|lesson_learned
    tags: list[str] = []
    is_public: bool = True


class KnowledgeNoteResponse(BaseModel):
    note_id: int
    chip_id: int | None
    content: str
    note_type: str
    tags: list[str]
    is_public: bool
    author_id: int = 0


# In-memory store for testing (replaced by PG+Milvus in integration)
_notes: dict[int, dict[str, Any]] = {}
_next_id = 1


@router.post("", response_model=KnowledgeNoteResponse)
async def create_note(note: KnowledgeNoteCreate) -> KnowledgeNoteResponse:
    global _next_id
    note_id = _next_id
    _next_id += 1
    data = {
        "note_id": note_id,
        "chip_id": note.chip_id,
        "content": note.content,
        "note_type": note.note_type,
        "tags": note.tags,
        "is_public": note.is_public,
        "author_id": 0,
    }
    _notes[note_id] = data
    return KnowledgeNoteResponse(**data)


@router.get("")
async def list_notes(
    chip_id: int | None = None, tags: str | None = None
) -> dict[str, Any]:
    results = list(_notes.values())
    if chip_id is not None:
        results = [n for n in results if n["chip_id"] == chip_id]
    if tags:
        tag_list = tags.split(",")
        results = [n for n in results if any(t in n["tags"] for t in tag_list)]
    return {"notes": results, "total": len(results)}


@router.get("/{note_id}", response_model=KnowledgeNoteResponse)
async def get_note(note_id: int) -> KnowledgeNoteResponse:
    if note_id not in _notes:
        raise HTTPException(404, "Note not found")
    return KnowledgeNoteResponse(**_notes[note_id])


@router.put("/{note_id}", response_model=KnowledgeNoteResponse)
async def update_note(note_id: int, note: KnowledgeNoteCreate) -> KnowledgeNoteResponse:
    if note_id not in _notes:
        raise HTTPException(404, "Note not found")
    _notes[note_id].update(
        content=note.content, note_type=note.note_type, tags=note.tags, is_public=note.is_public
    )
    return KnowledgeNoteResponse(**_notes[note_id])


@router.delete("/{note_id}")
async def delete_note(note_id: int) -> dict[str, str]:
    if note_id not in _notes:
        raise HTTPException(404, "Note not found")
    del _notes[note_id]
    return {"status": "deleted"}
