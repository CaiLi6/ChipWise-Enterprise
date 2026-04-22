"""Numeric grounding + retrieval quality gating.

Two jobs:

1. **Numeric grounding** — extract all `<number> <unit>` tokens from an answer
   and verify each appears in the retrieved chunks. Catches hallucinations
   like "125 MHz ± 3%" when chunks only mention "62.5 / 125 / 250 MHz".
2. **Retrieval quality gate** — cheap heuristic over top-K scores that marks
   a query as low-evidence so the response layer can abstain.

Deliberately regex-based (no LLM): runs synchronously per request, adds ~1 ms.
The LLM-judge remains the deeper (but slower) safety net upstream.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Units
# ---------------------------------------------------------------------------

# Canonical unit families. Variants on the right all normalize to the left.
_UNIT_ALIASES: dict[str, tuple[str, ...]] = {
    "hz":   ("hz",),
    "khz":  ("khz",),
    "mhz":  ("mhz", "兆赫"),
    "ghz":  ("ghz", "吉赫"),
    "bps":  ("bps",),
    "kbps": ("kbps",),
    "mbps": ("mbps", "mb/s"),
    "gbps": ("gbps", "gb/s"),
    "gt/s": ("gt/s", "gts"),
    "b":    ("bit", "bits", "b"),
    "kb":   ("kb", "kbit"),
    "mb":   ("mb", "mbit"),
    "gb":   ("gb", "gbit"),
    "byte": ("byte", "bytes", "字节"),
    "v":    ("v",),
    "mv":   ("mv",),
    "a":    ("a",),
    "ma":   ("ma",),
    "ua":   ("ua", "μa"),
    "w":    ("w",),
    "mw":   ("mw",),
    "c":    ("°c", "℃"),
    "ns":   ("ns",),
    "us":   ("us", "μs"),
    "ms":   ("ms",),
    "s":    ("s", "sec"),
    "pct":  ("%",),
    "dB":   ("db",),
    "mm":   ("mm",),
    "pin":  ("pin", "pins", "引脚", "pins"),
    "x":    ("x",),   # lane width: x1/x4/x8/x16
}

_ALIAS_TO_CANON: dict[str, str] = {alias: canon for canon, aliases in _UNIT_ALIASES.items() for alias in aliases}

# Longest-first so "mhz" beats "m" etc.
_UNIT_PATTERN = "|".join(sorted({re.escape(a) for a in _ALIAS_TO_CANON}, key=len, reverse=True))

# Matches optional sign, integer/decimal with commas, and a unit (or lane x1/x8).
# Groups: 1=number, 2=unit
_FACT_RE = re.compile(
    r"(?<![\w.])([+-]?\d[\d,]*(?:\.\d+)?)\s*(" + _UNIT_PATTERN + r")\b",
    re.IGNORECASE,
)

# Lane shorthand like x8 / x16 appears without a number-space-unit form.
_LANE_RE = re.compile(r"(?<![\w.])x(\d+)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class NumericFact:
    value: float
    unit: str  # canonical form ("mhz", "gbps", ...)
    raw: str   # original surface form from the answer

    def __str__(self) -> str:  # for logs / UI
        return self.raw


@dataclass
class GroundingReport:
    supported: list[NumericFact] = field(default_factory=list)
    unsupported: list[NumericFact] = field(default_factory=list)
    total: int = 0
    coverage: float = 1.0  # supported / total — 1.0 when no facts to check
    retrieval_score: float = 0.0  # top-1 rerank/cosine score [0..1]
    retrieval_mean: float = 0.0
    retrieval_ok: bool = True
    abstain: bool = False
    reason: str = ""

    def summary_banner(self) -> str:
        """Render a short markdown banner if anything is off."""
        if self.abstain:
            return (
                f"> ⚠️ **证据不足** — {self.reason} "
                f"建议重述问题或补充更具体的芯片型号/参数名。"
            )
        if not self.unsupported:
            return ""
        shown = ", ".join(f"`{f.raw}`" for f in self.unsupported[:5])
        more = "" if len(self.unsupported) <= 5 else f"（共 {len(self.unsupported)} 处）"
        return f"> ⚠️ **未在引用材料中找到数值**: {shown}{more} — 请核实原 datasheet。"


# ---------------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------------


def _normalize(text: str) -> str:
    """Lowercase + NFKC + collapse spaces around slashes so 'Mb/s'↔'mb/s'."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text).lower()
    text = text.replace("\u00a0", " ")  # NBSP → normal space
    text = re.sub(r"\s*/\s*", "/", text)
    return text


def _parse_number(raw: str) -> float | None:
    try:
        return float(raw.replace(",", ""))
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


def extract_numeric_facts(text: str) -> list[NumericFact]:
    """Pull out every `<number> <unit>` occurrence from *text*.

    Duplicates are preserved so that coverage maths work on occurrences, not
    unique facts. Lane shorthand (`x8`, `x16`) maps to unit ``x``.
    """
    if not text:
        return []
    out: list[NumericFact] = []
    norm = _normalize(text)

    for m in _FACT_RE.finditer(norm):
        number = _parse_number(m.group(1))
        if number is None:
            continue
        unit = _ALIAS_TO_CANON.get(m.group(2).lower(), m.group(2).lower())
        raw_slice = text[m.start():m.end()].strip()
        out.append(NumericFact(value=number, unit=unit, raw=raw_slice))

    for m in _LANE_RE.finditer(norm):
        number = _parse_number(m.group(1))
        if number is None:
            continue
        raw_slice = text[m.start():m.end()].strip()
        out.append(NumericFact(value=number, unit="x", raw=raw_slice))

    return out


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def _fact_in_chunks(fact: NumericFact, chunk_index: Iterable[tuple[float, str]], rel_tol: float = 0.01) -> bool:
    """Return True iff *fact* appears in any chunk (normalized).

    *chunk_index* is a list of ``(value, canonical_unit)`` pairs precomputed
    from the retrieved chunks. Relative tolerance handles ``125.0 MHz`` vs
    ``125 MHz`` and similar. Exact match required for integers (lane width,
    pin counts).
    """
    for val, unit in chunk_index:
        if unit != fact.unit:
            continue
        if fact.value == 0.0 or val == 0.0:
            if val == fact.value:
                return True
            continue
        if abs(val - fact.value) / max(abs(fact.value), abs(val)) <= rel_tol:
            return True
    return False


def _index_chunks(chunks: Sequence[str]) -> list[tuple[float, str]]:
    index: list[tuple[float, str]] = []
    for c in chunks:
        norm = _normalize(c)
        for m in _FACT_RE.finditer(norm):
            val = _parse_number(m.group(1))
            if val is None:
                continue
            unit = _ALIAS_TO_CANON.get(m.group(2).lower(), m.group(2).lower())
            index.append((val, unit))
        for m in _LANE_RE.finditer(norm):
            val = _parse_number(m.group(1))
            if val is None:
                continue
            index.append((val, "x"))
    return index


# ---------------------------------------------------------------------------
# Retrieval quality gate
# ---------------------------------------------------------------------------


@dataclass
class RetrievalGateConfig:
    min_citations: int = 2
    min_top_score: float = 0.35
    min_mean_score: float = 0.25
    max_unsupported_ratio: float = 0.40  # >40% unverified numbers → abstain
    enabled: bool = True


def _retrieval_signal(citations: Sequence[dict]) -> tuple[float, float]:
    """Return (top_score, mean_score) over citation list."""
    scores: list[float] = []
    for c in citations:
        try:
            s = float(c.get("score", 0.0) or 0.0)
        except (TypeError, ValueError):
            continue
        if s > 0:
            scores.append(s)
    if not scores:
        return 0.0, 0.0
    return max(scores), sum(scores) / len(scores)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


_EARLY_STOP_REASONS = {
    "token_budget_exhausted": "Agent 在检索过程中用尽了 token 预算",
    "max_iterations": "Agent 达到最大迭代次数仍未收敛",
}


def check_grounding(
    answer: str,
    citations: Sequence[dict],
    config: RetrievalGateConfig | None = None,
    stopped_reason: str | None = None,
) -> GroundingReport:
    """End-to-end check: build report, decide abstention.

    - If ``stopped_reason`` indicates early termination (budget / iterations),
      abstain immediately — the answer string is a sentinel, not a real answer.
    - Retrieval gate runs next (cheap, can trigger abstain without parsing
      the answer).
    - Numeric grounding runs over whatever citations we have.
    - ``report.abstain`` is True when evidence is too thin to trust the
      answer. The caller is expected to replace or decorate the answer text.
    """
    cfg = config or RetrievalGateConfig()
    top_score, mean_score = _retrieval_signal(citations)

    report = GroundingReport(
        retrieval_score=top_score,
        retrieval_mean=mean_score,
    )

    # Stage 0 — early-stop sentinel from orchestrator
    if cfg.enabled and stopped_reason in _EARLY_STOP_REASONS:
        report.abstain = True
        report.retrieval_ok = False
        report.reason = _EARLY_STOP_REASONS[stopped_reason]
        return report

    # Stage 1 — retrieval quality gate
    if cfg.enabled:
        if len(citations) < cfg.min_citations:
            report.abstain = True
            report.retrieval_ok = False
            report.reason = f"仅检索到 {len(citations)} 条引用（要求 ≥{cfg.min_citations}）"
            return report
        if top_score and top_score < cfg.min_top_score:
            report.abstain = True
            report.retrieval_ok = False
            report.reason = (
                f"top-1 相关度 {top_score:.2f} 低于阈值 {cfg.min_top_score:.2f}"
            )
            return report
        if mean_score and mean_score < cfg.min_mean_score:
            report.abstain = True
            report.retrieval_ok = False
            report.reason = (
                f"平均相关度 {mean_score:.2f} 低于阈值 {cfg.min_mean_score:.2f}"
            )
            return report

    # Stage 2 — numeric grounding
    facts = extract_numeric_facts(answer)
    report.total = len(facts)
    if not facts:
        report.coverage = 1.0
        return report

    chunk_texts = [str(c.get("content") or "") for c in citations]
    index = _index_chunks(chunk_texts)

    for f in facts:
        if _fact_in_chunks(f, index):
            report.supported.append(f)
        else:
            report.unsupported.append(f)

    report.coverage = len(report.supported) / len(facts) if facts else 1.0

    if cfg.enabled and report.total >= 3:
        unsupported_ratio = len(report.unsupported) / report.total
        if unsupported_ratio > cfg.max_unsupported_ratio:
            report.abstain = True
            report.reason = (
                f"{len(report.unsupported)}/{report.total} 个数值无法在引用中找到依据"
            )

    return report


def annotate_answer(answer: str, report: GroundingReport, abstain_template: str | None = None) -> str:
    """Attach a warning banner to *answer* when grounding is imperfect.

    When ``report.abstain`` is True, replace the answer with the abstain
    template to avoid propagating a low-confidence response.
    """
    if report.abstain:
        tmpl = abstain_template or (
            "## 结论\n\n暂无法给出可靠答案。\n\n"
            "## 原因\n\n{reason}\n\n"
            "## 建议\n\n- 补充具体芯片型号或参数名\n"
            "- 重新上传相关 datasheet 后再试\n"
            "- 或联系知识库管理员补全该领域文档"
        )
        return tmpl.format(reason=report.reason or "证据不足")

    banner = report.summary_banner()
    if banner:
        return f"{banner}\n\n{answer}"
    return answer
