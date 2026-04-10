#!/usr/bin/env python3
"""
Spec Sync — splits ENTERPRISE_DEV_SPEC.md into chapter-based reference files
under auto-coder/references/, and copies DEVELOPMENT_PLAN.md as 06-schedule.md.

Sources:
    docs/ENTERPRISE_DEV_SPEC.md  → references/00-metadata.md, 01-05.md, 07-appendix.md
    docs/DEVELOPMENT_PLAN.md     → references/06-schedule.md (with §6 overview header)

Usage:
    python .github/skills/auto-coder/scripts/sync_spec.py [--force]
"""

import hashlib
import re
import sys
from pathlib import Path
from typing import List, Tuple, NamedTuple


class Chapter(NamedTuple):
    number: int
    cn_title: str
    filename: str
    start_line: int
    end_line: int
    line_count: int


# Chapter number -> English slug (encoding-independent)
# Matches ENTERPRISE_DEV_SPEC.md structure:
#   §1 项目概述 | §2 核心特点 | §3 技术选型 | §4 系统架构与模块设计
#   §5 测试方案与可观测性 | §6 项目排期 (replaced by DEVELOPMENT_PLAN) | §7 附录
NUMBER_SLUG_MAP = {
    1: "overview",
    2: "features",
    3: "tech-stack",
    4: "architecture",
    5: "testing",
    6: "schedule",   # §6 overview is prepended; body is DEVELOPMENT_PLAN.md
    7: "appendix",
}

# Chapter 6 body is provided by DEVELOPMENT_PLAN.md; its DEV_SPEC overview
# is prepended as a header in 06-schedule.md.
SKIP_CHAPTERS = {6}

# Files that must exist at repo root for validation
REQUIRED_DOCS = ("docs/ENTERPRISE_DEV_SPEC.md", "docs/DEVELOPMENT_PLAN.md")


def _slug(chapter_num: int, title: str) -> str:
    if chapter_num in NUMBER_SLUG_MAP:
        return NUMBER_SLUG_MAP[chapter_num]
    clean = re.sub(r'[^\w]+', '-', title, flags=re.ASCII).strip('-').lower()
    return clean or f"chapter-{chapter_num}"


def _find_repo_root(skill_dir: Path) -> Path:
    """Walk up from skill_dir to find the repo root containing docs/."""
    candidate = skill_dir
    for _ in range(6):
        candidate = candidate.parent
        if all((candidate / p).exists() for p in REQUIRED_DOCS):
            return candidate
    # Fallback: legacy 3-level parent (auto-coder → skills → .github → root)
    legacy = skill_dir.parent.parent.parent
    if all((legacy / p).exists() for p in REQUIRED_DOCS):
        return legacy
    print(f"ERROR: cannot locate repo root from {skill_dir}")
    print(f"  Expected files: {', '.join(REQUIRED_DOCS)}")
    sys.exit(1)


def detect_chapters(content: str) -> List[Chapter]:
    """Detect top-level chapters using '# N. Title' format (single #)."""
    lines = content.split('\n')
    starts: List[Tuple[int, str, int]] = []
    for i, line in enumerate(lines):
        m = re.match(r'^# (\d+)\.\s+(.+)$', line)
        if m:
            starts.append((int(m.group(1)), m.group(2).strip(), i))
    if not starts:
        raise ValueError(
            "No chapters found. Expected '# N. Title' format in ENTERPRISE_DEV_SPEC.md"
        )
    chapters = []
    for idx, (num, title, start) in enumerate(starts):
        end = starts[idx + 1][2] if idx + 1 < len(starts) else len(lines)
        chapters.append(Chapter(num, title, f"{num:02d}-{_slug(num, title)}.md", start, end, end - start))
    return chapters


def sync(force: bool = False):
    skill_dir = Path(__file__).resolve().parent.parent   # auto-coder/
    repo_root = _find_repo_root(skill_dir)
    dev_spec  = repo_root / "docs" / "ENTERPRISE_DEV_SPEC.md"
    dev_plan  = repo_root / "docs" / "DEVELOPMENT_PLAN.md"
    specs_dir = skill_dir / "references"
    hash_file = skill_dir / ".spec_hash"

    # Hash both source files together
    combined_hash = hashlib.sha256(
        dev_spec.read_bytes() + dev_plan.read_bytes()
    ).hexdigest()

    if not force and hash_file.exists() and hash_file.read_text().strip() == combined_hash:
        print("specs up-to-date"); return

    # --- Process ENTERPRISE_DEV_SPEC.md ---
    content = dev_spec.read_text(encoding='utf-8')
    chapters = detect_chapters(content)
    lines = content.split('\n')

    specs_dir.mkdir(parents=True, exist_ok=True)

    # Expected output files
    expected_files = {ch.filename for ch in chapters if ch.number not in SKIP_CHAPTERS}
    expected_files.add("00-metadata.md")
    expected_files.add("06-schedule.md")

    # Clean orphan reference files
    for f in {f.name for f in specs_dir.glob("*.md")} - expected_files:
        (specs_dir / f).unlink()

    # --- 00-metadata.md: pre-chapter content (title, version, changelog, TOC) ---
    first_chapter_line = chapters[0].start_line if chapters else len(lines)
    metadata = '\n'.join(lines[:first_chapter_line]).rstrip()
    if metadata:
        (specs_dir / "00-metadata.md").write_text(metadata, encoding='utf-8')

    # --- Write DEV_SPEC chapters (skip §6 body — see below) ---
    written_spec = 0
    sec6_overview = ""
    for ch in chapters:
        if ch.number in SKIP_CHAPTERS:
            # Capture §6 overview to prepend to 06-schedule.md
            sec6_overview = '\n'.join(lines[ch.start_line:ch.end_line]).rstrip()
            continue
        (specs_dir / ch.filename).write_text(
            '\n'.join(lines[ch.start_line:ch.end_line]), encoding='utf-8'
        )
        written_spec += 1

    # --- 06-schedule.md: §6 overview header + DEVELOPMENT_PLAN.md ---
    plan_content = dev_plan.read_text(encoding='utf-8')
    schedule_parts = []
    if sec6_overview:
        schedule_parts.append(sec6_overview)
        schedule_parts.append("\n\n---\n\n"
                             "> 以下为 `docs/DEVELOPMENT_PLAN.md` 完整内容（详细任务排期）\n")
    schedule_parts.append(plan_content)
    (specs_dir / "06-schedule.md").write_text('\n'.join(schedule_parts), encoding='utf-8')

    hash_file.write_text(combined_hash)
    total = written_spec + 2  # +2 for 00-metadata.md and 06-schedule.md
    print(f"synced {total} files ({written_spec} chapters + 00-metadata + 06-schedule)")


if __name__ == "__main__":
    sync(force="--force" in sys.argv)
