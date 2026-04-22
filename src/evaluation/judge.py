"""LLM-as-judge metric runners for Agentic RAG.

Direct LM Studio prompting — no hard dependency on RAGAS. The RAGAS library
is kept as an optional alternative runner in ``ragas_judge.py``.

Why direct prompting:
- Our corpus is Chinese datasheets; we want Chinese-aware rubrics
- Router 1.7B needs very short prompts for stable output; we keep it concise
- Avoids the LangChain wrapper indirection

All judges output a single JSON object that we parse defensively (best-effort
regex fallback when the model forgets the fences).
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

from src.libs.llm.base import BaseLLM

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Prompts (kept intentionally short for router 1.7B stability)
# ---------------------------------------------------------------------------

_PROMPT_FAITHFULNESS = """你是 RAG 忠实度评审。给定【问题】【参考材料】【回答】，
判断回答中每个事实性断言是否能从参考材料中推出。
输出严格 JSON：{{"supported": N, "unsupported": N, "score": 0-1 小数}}
只输出一行 JSON，不要解释。

【问题】{question}
【参考材料】{contexts}
【回答】{answer}
"""

_PROMPT_RELEVANCY = """你是 RAG 相关性评审。判断【回答】是否正面回答了【问题】。
1=完全跑题 2=部分相关 3=基本回答 4=完整回答 5=完整且精确
输出严格 JSON：{{"rating": 1-5, "score": 0-1 小数, "reason": "<=15 字"}}
只输出一行 JSON，不要解释。

【问题】{question}
【回答】{answer}
"""

_PROMPT_CONTEXT_PRECISION = """你是 RAG 检索精度评审。对每段【参考材料】判断是否与【问题】相关。
输出严格 JSON：{{"relevant": [0/1, 0/1, ...], "score": 0-1 小数}}
数组长度必须等于参考材料数。分数 = 相关数 / 总数。
只输出一行 JSON，不要解释。

【问题】{question}
【参考材料】{contexts_numbered}
"""

_PROMPT_CONTEXT_RECALL = """你是 RAG 检索召回评审。判断【标准答案】中的关键事实是否都能在【参考材料】中找到依据。
输出严格 JSON：{{"covered": N, "missing": N, "score": 0-1 小数}}
只输出一行 JSON，不要解释。

【问题】{question}
【参考材料】{contexts}
【标准答案】{ground_truth}
"""


# ---------------------------------------------------------------------------
# Structures
# ---------------------------------------------------------------------------


@dataclass
class JudgeOutput:
    metric: str
    score: float | None
    raw: str
    parsed: dict[str, Any] | None
    error: str | None = None
    latency_ms: float = 0.0


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


_JSON_RE = re.compile(r"\{[^{}]*\}", re.DOTALL)
_FENCED_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _parse_json(raw: str) -> dict[str, Any] | None:
    """Parse the first JSON object found in raw text; None on failure.

    Tries, in order: fenced code block, full raw text, last non-empty
    ``{...}`` substring. Scans last-match-wins because thinking models often
    deliberate before emitting the answer at the end.
    """
    if not raw:
        return None
    candidates: list[str] = []
    fenced = _FENCED_RE.findall(raw)
    if fenced:
        candidates.extend(reversed(fenced))
    candidates.append(raw.strip())
    matches = _JSON_RE.findall(raw)
    if matches:
        # Reverse so the last JSON object in the output wins (usually the final answer)
        candidates.extend(reversed(matches))
    for c in candidates:
        try:
            obj = json.loads(c)
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            continue
    return None


def _truncate(text: str, n: int = 1200) -> str:
    if not text:
        return ""
    return text[:n] + ("..." if len(text) > n else "")


def _join_contexts(contexts: list[str], per_chunk: int = 400, max_n: int = 4) -> str:
    cut = contexts[:max_n]
    return "\n---\n".join(f"[{i + 1}] {_truncate(c, per_chunk)}" for i, c in enumerate(cut))


async def _call_judge(llm: BaseLLM, prompt: str, max_tokens: int = 256, temperature: float = 0.0) -> tuple[str, float]:
    """Invoke the judge LLM with qwen3 thinking-mode compatibility.

    - Append ``/no_think`` to nudge qwen3 into direct output.
    - If content is still empty (thinking model didn't emit final text),
      read ``reasoning_content`` and try to parse a JSON object out of it.
    """
    t0 = time.time()
    prompt_final = prompt.rstrip() + "\n/no_think\n"
    try:
        resp = await llm.generate(prompt_final, temperature=temperature, max_tokens=max_tokens)
        text = (resp.text or "").strip()
        if not text and resp.raw:
            try:
                msg = resp.raw["choices"][0]["message"]
                text = (msg.get("reasoning_content") or "").strip()
            except (KeyError, IndexError, TypeError):
                pass
    except Exception as exc:  # noqa: BLE001
        body = getattr(getattr(exc, "response", None), "text", "")
        logger.warning("judge LLM call failed: %s | body=%s | prompt_len=%d", exc, body[:400], len(prompt_final))
        text = ""
    return text, (time.time() - t0) * 1000


async def judge_faithfulness(
    llm: BaseLLM, question: str, answer: str, contexts: list[str]
) -> JudgeOutput:
    if not answer or not contexts:
        return JudgeOutput("faithfulness", None, "", None, error="empty_input")
    prompt = _PROMPT_FAITHFULNESS.format(
        question=_truncate(question, 300),
        contexts=_join_contexts(contexts),
        answer=_truncate(answer, 1500),
    )
    raw, ms = await _call_judge(llm, prompt, max_tokens=384)
    parsed = _parse_json(raw)
    score = None
    if parsed is not None:
        s = parsed.get("score")
        if isinstance(s, int | float):
            score = max(0.0, min(1.0, float(s)))
        elif "supported" in parsed and "unsupported" in parsed:
            try:
                sup = float(parsed["supported"])
                unsup = float(parsed["unsupported"])
                total = sup + unsup
                score = sup / total if total > 0 else None
            except (TypeError, ValueError):
                pass
    return JudgeOutput("faithfulness", score, raw, parsed, latency_ms=ms)


async def judge_relevancy(llm: BaseLLM, question: str, answer: str) -> JudgeOutput:
    if not answer or not question:
        return JudgeOutput("answer_relevancy", None, "", None, error="empty_input")
    prompt = _PROMPT_RELEVANCY.format(
        question=_truncate(question, 300),
        answer=_truncate(answer, 1500),
    )
    raw, ms = await _call_judge(llm, prompt, max_tokens=384)
    parsed = _parse_json(raw)
    score = None
    if parsed is not None:
        s = parsed.get("score")
        if isinstance(s, int | float):
            score = max(0.0, min(1.0, float(s)))
        else:
            r = parsed.get("rating")
            if isinstance(r, int | float):
                score = max(0.0, min(1.0, (float(r) - 1) / 4))
    return JudgeOutput("answer_relevancy", score, raw, parsed, latency_ms=ms)


async def judge_context_precision(
    llm: BaseLLM, question: str, contexts: list[str]
) -> JudgeOutput:
    if not contexts:
        return JudgeOutput("context_precision", None, "", None, error="empty_input")
    prompt = _PROMPT_CONTEXT_PRECISION.format(
        question=_truncate(question, 300),
        contexts_numbered=_join_contexts(contexts),
    )
    raw, ms = await _call_judge(llm, prompt, max_tokens=384)
    parsed = _parse_json(raw)
    score = None
    if parsed is not None:
        s = parsed.get("score")
        if isinstance(s, int | float):
            score = max(0.0, min(1.0, float(s)))
        else:
            rel = parsed.get("relevant")
            if isinstance(rel, list) and rel:
                try:
                    ones = sum(1 for v in rel if float(v) >= 0.5)
                    score = ones / len(rel)
                except (TypeError, ValueError):
                    pass
    return JudgeOutput("context_precision", score, raw, parsed, latency_ms=ms)


async def judge_context_recall(
    llm: BaseLLM, question: str, contexts: list[str], ground_truth: str
) -> JudgeOutput:
    if not contexts or not ground_truth:
        return JudgeOutput("context_recall", None, "", None, error="empty_input")
    prompt = _PROMPT_CONTEXT_RECALL.format(
        question=_truncate(question, 300),
        contexts=_join_contexts(contexts),
        ground_truth=_truncate(ground_truth, 800),
    )
    raw, ms = await _call_judge(llm, prompt, max_tokens=384)
    parsed = _parse_json(raw)
    score = None
    if parsed is not None:
        s = parsed.get("score")
        if isinstance(s, int | float):
            score = max(0.0, min(1.0, float(s)))
        elif "covered" in parsed and "missing" in parsed:
            try:
                cov = float(parsed["covered"])
                miss = float(parsed["missing"])
                total = cov + miss
                score = cov / total if total > 0 else None
            except (TypeError, ValueError):
                pass
    return JudgeOutput("context_recall", score, raw, parsed, latency_ms=ms)
