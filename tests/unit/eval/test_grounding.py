"""Unit tests for src/evaluation/grounding.py."""

from __future__ import annotations

import pytest
from src.evaluation.grounding import (
    GroundingReport,
    RetrievalGateConfig,
    annotate_answer,
    check_grounding,
    extract_numeric_facts,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Extraction
# ---------------------------------------------------------------------------


class TestExtract:
    def test_basic_mhz(self) -> None:
        facts = extract_numeric_facts("SPI max clock 125 MHz")
        assert len(facts) == 1
        assert facts[0].value == 125.0
        assert facts[0].unit == "mhz"

    def test_decimal_and_comma(self) -> None:
        facts = extract_numeric_facts("DSP blocks 1,800 pin; core 1.2 V; 2.5 GT/s")
        units = [f.unit for f in facts]
        values = [f.value for f in facts]
        assert "pin" in units
        assert "v" in units
        assert "gt/s" in units
        assert 1800.0 in values
        assert 1.2 in values
        assert 2.5 in values

    def test_unit_aliases(self) -> None:
        # Mb/s, mbps, MBPS, 兆字节 — all should normalize
        facts = extract_numeric_facts("link 500 Mb/s and 100 mbps")
        assert len(facts) == 2
        assert all(f.unit == "mbps" for f in facts)

    def test_lane_width(self) -> None:
        facts = extract_numeric_facts("PCIe Gen4 x8 and x16 supported")
        lane_vals = sorted(f.value for f in facts if f.unit == "x")
        assert lane_vals == [8.0, 16.0]

    def test_ignores_words_that_look_like_units(self) -> None:
        # "the" is not a unit; bare "100" without unit should not match.
        facts = extract_numeric_facts("There are 100 registers defined")
        assert facts == []

    def test_empty(self) -> None:
        assert extract_numeric_facts("") == []
        assert extract_numeric_facts(None) == []  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


def _cite(content: str, score: float = 0.8) -> dict:
    return {"chunk_id": content[:8], "content": content, "score": score}


class TestVerify:
    def test_all_supported(self) -> None:
        answer = "SPI max clock **125 MHz** over PCIe x8 at 5.0 GT/s"
        citations = [
            _cite("SPI clock 125 MHz per Table 2-10"),
            _cite("PCIe Gen3 x8 lanes at 5.0 GT/s"),
        ]
        report = check_grounding(answer, citations)
        assert not report.abstain
        assert report.coverage == 1.0
        assert not report.unsupported

    def test_hallucinated_number_flagged(self) -> None:
        # "3%" and "160 MHz" do not appear in chunks — must flag.
        answer = "Reference clock 125 MHz ± 3%, range 100-160 MHz"
        citations = [
            _cite("The reference clock supports 62.5 MHz, 125 MHz, 250 MHz"),
            _cite("Jitter spec defined in datasheet section 4"),
        ]
        report = check_grounding(answer, citations)
        unsupported_raws = " ".join(f.raw for f in report.unsupported).lower()
        assert "3%" in unsupported_raws or "160" in unsupported_raws
        # 125 MHz appears in chunks → should be supported
        assert any(f.value == 125.0 and f.unit == "mhz" for f in report.supported)

    def test_tolerance_handles_minor_formatting(self) -> None:
        answer = "Operating at 125.0 MHz"
        citations = [_cite("clock is 125 MHz"), _cite("also 125 MHz")]
        report = check_grounding(answer, citations)
        assert len(report.supported) == 1
        assert not report.unsupported
        assert not report.abstain

    def test_no_facts_is_full_coverage(self) -> None:
        answer = "这颗芯片适合工业场景。"
        citations = [_cite("datasheet text"), _cite("more text")]
        report = check_grounding(answer, citations)
        assert report.total == 0
        assert report.coverage == 1.0
        assert not report.abstain


# ---------------------------------------------------------------------------
# Retrieval gate
# ---------------------------------------------------------------------------


class TestRetrievalGate:
    def test_abstain_on_too_few_citations(self) -> None:
        report = check_grounding(
            "100 MHz",
            [_cite("junk", score=0.9)],
            config=RetrievalGateConfig(min_citations=2),
        )
        assert report.abstain
        assert "引用" in report.reason

    def test_abstain_on_low_top_score(self) -> None:
        report = check_grounding(
            "100 MHz",
            [_cite("a", score=0.10), _cite("b", score=0.08)],
            config=RetrievalGateConfig(min_top_score=0.35),
        )
        assert report.abstain
        assert "top-1" in report.reason

    def test_abstain_on_too_many_unsupported(self) -> None:
        answer = "Clock 111 MHz, bus 222 Gbps, rail 333 V, voltage 444 V"
        citations = [
            _cite("Some unrelated datasheet paragraph", score=0.8),
            _cite("Another unrelated chunk", score=0.7),
        ]
        report = check_grounding(
            answer, citations,
            config=RetrievalGateConfig(max_unsupported_ratio=0.3),
        )
        assert report.abstain
        assert "无法" in report.reason or "数值" in report.reason

    def test_disabled_gate_never_abstains(self) -> None:
        report = check_grounding(
            "100 MHz",
            [],
            config=RetrievalGateConfig(enabled=False),
        )
        assert not report.abstain


# ---------------------------------------------------------------------------
# Annotate
# ---------------------------------------------------------------------------


class TestAnnotate:
    def test_abstain_replaces_answer(self) -> None:
        rep = GroundingReport(abstain=True, reason="no chunks")
        out = annotate_answer("original answer", rep)
        assert "original answer" not in out
        assert "暂无法给出" in out
        assert "no chunks" in out

    def test_partial_prepends_banner(self) -> None:
        from src.evaluation.grounding import NumericFact

        rep = GroundingReport(
            supported=[NumericFact(125.0, "mhz", "125 MHz")],
            unsupported=[NumericFact(300.0, "mhz", "300 MHz")],
            total=2, coverage=0.5,
        )
        out = annotate_answer("## 结论\n\ndetails", rep)
        assert out.startswith("> ⚠️")
        assert "300 MHz" in out
        assert "## 结论" in out

    def test_clean_report_unchanged(self) -> None:
        rep = GroundingReport(total=0, coverage=1.0)
        assert annotate_answer("clean", rep) == "clean"


# ---------------------------------------------------------------------------
# Early-stop sentinel propagation
# ---------------------------------------------------------------------------


class TestEarlyStop:
    def test_token_budget_triggers_abstain(self) -> None:
        rep = check_grounding(
            "## 结论\n\nirrelevant body",
            citations=[{"chunk_id": "c1", "content": "anything"}] * 3,
            stopped_reason="token_budget_exhausted",
        )
        assert rep.abstain is True
        assert rep.retrieval_ok is False
        assert "token" in (rep.reason or "").lower() or "预算" in (rep.reason or "")

    def test_max_iterations_triggers_abstain(self) -> None:
        rep = check_grounding(
            "## 结论\n\nirrelevant body",
            citations=[{"chunk_id": "c1", "content": "anything"}] * 3,
            stopped_reason="max_iterations",
        )
        assert rep.abstain is True
        assert "迭代" in (rep.reason or "")

    def test_complete_does_not_force_abstain(self) -> None:
        rep = check_grounding(
            "answer with no numbers",
            citations=[{"chunk_id": "c1", "content": "something"}] * 3,
            stopped_reason="complete",
        )
        # No early-stop, no numeric facts, healthy citation count → not abstain.
        assert rep.abstain is False

    def test_disabled_config_bypasses_early_stop(self) -> None:
        cfg = RetrievalGateConfig(enabled=False)
        rep = check_grounding(
            "answer",
            citations=[],
            config=cfg,
            stopped_reason="token_budget_exhausted",
        )
        assert rep.abstain is False
