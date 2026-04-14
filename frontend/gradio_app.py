"""ChipWise Gradio MVP frontend (§6A1, §6A2, §6A3).

DEPRECATED: This Gradio MVP is retained for backward compatibility only.
Production frontend is frontend/web/ (Vue3 + Element Plus).
This file may be removed in a future release.
"""

from __future__ import annotations

import json
import logging
import warnings
from typing import Any

warnings.warn(
    "frontend/gradio_app.py is deprecated; use frontend/web/ (Vue3 + Element Plus)",
    DeprecationWarning,
    stacklevel=2,
)

logger = logging.getLogger(__name__)

try:
    import gradio as gr
    _HAS_GRADIO = True
except ImportError:
    _HAS_GRADIO = False
    gr = None  # type: ignore[assignment]


def create_gradio_app(api_base: str = "http://localhost:8080") -> Any:
    """Create Gradio multi-tab application.

    Args:
        api_base: Base URL for the ChipWise API server.

    Returns:
        gr.Blocks instance (or None if gradio not installed).
    """
    if not _HAS_GRADIO:
        logger.error("gradio not installed. Run: pip install gradio")
        return None

    import httpx

    def _auth_headers(token: str) -> dict[str, str]:
        return {"Authorization": f"Bearer {token}"} if token else {}

    # ── Tab 1: Chat Query ────────────────────────────────────────────────
    def chat_query(message: str, history: list, token: str) -> str:
        try:
            resp = httpx.post(
                f"{api_base}/api/v1/query",
                json={"query": message},
                headers=_auth_headers(token),
                timeout=60,
            )
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get("answer", data.get("response", str(data)))
                citations = data.get("citations", [])
                if citations:
                    refs = "\n".join(f"[{i+1}] {c.get('source', c)}" for i, c in enumerate(citations[:3]))
                    return f"{answer}\n\n**References:**\n{refs}"
                return answer
            return f"Error {resp.status_code}: {resp.text}"
        except Exception as e:
            return f"Connection error: {e}"

    # ── Tab 2: Document Upload ──────────────────────────────────────────
    def upload_document(file: Any, token: str) -> str:
        if file is None:
            return "No file selected."
        try:
            with open(file.name, "rb") as f:
                resp = httpx.post(
                    f"{api_base}/api/v1/documents/upload",
                    files={"file": (file.name, f, "application/octet-stream")},
                    headers=_auth_headers(token),
                    timeout=30,
                )
            if resp.status_code in (200, 201, 202):
                data = resp.json()
                task_id = data.get("task_id")
                return f"Upload started. Task ID: {task_id}\nStatus: {data.get('status', 'queued')}"
            return f"Upload failed ({resp.status_code}): {resp.text}"
        except Exception as e:
            return f"Error: {e}"

    def check_task_progress(task_id: str, token: str) -> str:
        if not task_id.strip():
            return "Enter a task ID."
        try:
            resp = httpx.get(
                f"{api_base}/api/v1/tasks/{task_id.strip()}",
                headers=_auth_headers(token),
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                prog = data.get("progress", 0)
                status = data.get("status", "unknown")
                return f"Task {task_id}\nStatus: {status}\nProgress: {prog}%"
            return f"Error {resp.status_code}: {resp.text}"
        except Exception as e:
            return f"Error: {e}"

    # ── Tab 3: Chip Compare ─────────────────────────────────────────────
    def chip_compare(chips_input: str, dimensions: str, token: str) -> str:
        names = [n.strip() for n in chips_input.split(",") if n.strip()]
        if len(names) < 2:
            return "Enter at least 2 chip part numbers separated by commas."
        dims = [d.strip() for d in dimensions.split(",") if d.strip()] if dimensions else None
        try:
            resp = httpx.post(
                f"{api_base}/api/v1/compare",
                json={"chip_names": names, "dimensions": dims},
                headers=_auth_headers(token),
                timeout=30,
            )
            if resp.status_code == 200:
                data = resp.json()
                table = data.get("comparison_table", {})
                analysis = data.get("analysis", "")
                lines = [f"## Chip Comparison: {', '.join(names)}\n"]
                if table:
                    lines.append("| Parameter | " + " | ".join(names) + " |")
                    lines.append("|" + "---|" * (len(names) + 1))
                    for param, vals in table.items():
                        row = [param]
                        for chip in names:
                            v = vals.get(chip)
                            row.append(f"{v.get('typ','N/A')} {v.get('unit','')}" if isinstance(v, dict) else "N/A")
                        lines.append("| " + " | ".join(row) + " |")
                if analysis:
                    lines.append(f"\n**Analysis:**\n{analysis}")
                return "\n".join(lines)
            return f"Error {resp.status_code}: {resp.text}"
        except Exception as e:
            return f"Error: {e}"

    # ── Tab 4: BOM Review ───────────────────────────────────────────────
    def bom_review(file: Any, token: str) -> str:
        if file is None:
            return "No BOM file selected."
        try:
            with open(file.name, "rb") as f:
                resp = httpx.post(
                    f"{api_base}/api/v1/bom/review",
                    files={"file": (file.name, f)},
                    headers=_auth_headers(token),
                    timeout=60,
                )
            if resp.status_code == 200:
                data = resp.json()
                summary = data.get("bom_review", {})
                lines = [
                    f"## BOM Review Results",
                    f"- Total items: {summary.get('total_items', 0)}",
                    f"- Matched: {summary.get('matched', 0)}",
                    f"- Unmatched: {summary.get('unmatched', 0)}",
                    f"- EOL warnings: {summary.get('eol_warnings', 0)}",
                    f"- Conflicts: {summary.get('conflicts', 0)}",
                ]
                items = data.get("items", [])
                warnings = [i for i in items if i.get("eol_flag") or i.get("nrnd_flag")]
                if warnings:
                    lines.append("\n**EOL/NRND Items:**")
                    for w in warnings[:10]:
                        flag = "EOL" if w.get("eol_flag") else "NRND"
                        lines.append(f"- Row {w['row_number']}: {w['part_number']} [{flag}]")
                return "\n".join(lines)
            return f"Error {resp.status_code}: {resp.text}"
        except Exception as e:
            return f"Error: {e}"

    # ── Tab 5: Knowledge Base ───────────────────────────────────────────
    def search_knowledge(query: str, token: str) -> str:
        try:
            resp = httpx.get(
                f"{api_base}/api/v1/knowledge",
                params={"search": query} if query else {},
                headers=_auth_headers(token),
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                notes = data.get("notes", [])
                if not notes:
                    return "No knowledge notes found."
                return "\n\n".join(
                    f"**#{n['note_id']}** [{n['note_type']}]\n{n['content']}"
                    for n in notes[:10]
                )
            return f"Error {resp.status_code}"
        except Exception as e:
            return f"Error: {e}"

    def create_knowledge_note(content: str, note_type: str, tags_str: str, token: str) -> str:
        if not content.strip():
            return "Content cannot be empty."
        tags = [t.strip() for t in tags_str.split(",") if t.strip()]
        try:
            resp = httpx.post(
                f"{api_base}/api/v1/knowledge",
                json={"content": content, "note_type": note_type, "tags": tags},
                headers=_auth_headers(token),
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                return f"Note created with ID: {data['note_id']}"
            return f"Error {resp.status_code}: {resp.text}"
        except Exception as e:
            return f"Error: {e}"

    # ── Tab 6: System Monitor ───────────────────────────────────────────
    def refresh_system_status(token: str) -> str:
        try:
            resp = httpx.get(f"{api_base}/readiness", headers=_auth_headers(token), timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                lines = [f"## System Status: **{data.get('status','unknown').upper()}**\n"]
                for svc, detail in data.get("services", {}).items():
                    icon = "✅" if detail.get("healthy") else "❌"
                    lines.append(f"{icon} **{svc}**: {detail.get('message','')}")
                return "\n".join(lines)
            return f"Error {resp.status_code}"
        except Exception as e:
            return f"Cannot reach API: {e}"

    # ── Build Blocks ────────────────────────────────────────────────────
    with gr.Blocks(title="ChipWise Enterprise", theme=gr.themes.Soft()) as app:
        gr.Markdown("# ChipWise Enterprise\n*Semiconductor Intelligence Platform*")

        token_box = gr.Textbox(
            label="JWT Token (paste after login)", type="password",
            placeholder="Bearer token...", scale=1
        )

        with gr.Tabs():
            # Tab 1: Chat
            with gr.Tab("💬 Chat Query"):
                chatbot = gr.ChatInterface(
                    fn=lambda msg, hist: chat_query(msg, hist, token_box.value),
                    chatbot=gr.Chatbot(height=400),
                    title="Ask about chips",
                )

            # Tab 2: Document Upload
            with gr.Tab("📄 Document Upload"):
                with gr.Row():
                    doc_file = gr.File(label="Select PDF", file_types=[".pdf"])
                    upload_btn = gr.Button("Upload", variant="primary")
                upload_output = gr.Markdown()
                with gr.Row():
                    task_id_box = gr.Textbox(label="Task ID (from upload)", placeholder="task-xxx")
                    check_btn = gr.Button("Check Progress")
                progress_output = gr.Markdown()
                upload_btn.click(upload_document, inputs=[doc_file, token_box], outputs=upload_output)
                check_btn.click(check_task_progress, inputs=[task_id_box, token_box], outputs=progress_output)

            # Tab 3: Chip Compare
            with gr.Tab("⚖️ Chip Compare"):
                chips_in = gr.Textbox(label="Chip part numbers (comma-separated)", placeholder="STM32F407, GD32F407")
                dims_in = gr.Textbox(label="Dimensions filter (optional)", placeholder="electrical, timing")
                compare_btn = gr.Button("Compare", variant="primary")
                compare_output = gr.Markdown()
                compare_btn.click(chip_compare, inputs=[chips_in, dims_in, token_box], outputs=compare_output)

            # Tab 4: BOM Review
            with gr.Tab("📋 BOM Review"):
                bom_file = gr.File(label="BOM Excel file", file_types=[".xlsx", ".xls", ".csv"])
                bom_btn = gr.Button("Review BOM", variant="primary")
                bom_output = gr.Markdown()
                bom_btn.click(bom_review, inputs=[bom_file, token_box], outputs=bom_output)

            # Tab 5: Knowledge Base
            with gr.Tab("📚 Knowledge Base"):
                with gr.Row():
                    kw_query = gr.Textbox(label="Search notes", placeholder="STM32 SPI timing...")
                    kw_btn = gr.Button("Search")
                kw_output = gr.Markdown()
                gr.Markdown("### Add a Note")
                with gr.Row():
                    note_content = gr.Textbox(label="Note content", lines=3)
                    note_type_dd = gr.Dropdown(
                        choices=["comment", "design_tip", "errata_link", "lesson_learned", "tag"],
                        value="design_tip", label="Type"
                    )
                note_tags = gr.Textbox(label="Tags (comma-separated)", placeholder="SPI, timing")
                note_btn = gr.Button("Save Note", variant="primary")
                note_output = gr.Textbox(label="Result", interactive=False)
                kw_btn.click(search_knowledge, inputs=[kw_query, token_box], outputs=kw_output)
                note_btn.click(create_knowledge_note, inputs=[note_content, note_type_dd, note_tags, token_box], outputs=note_output)

            # Tab 6: System Monitor
            with gr.Tab("🔧 System Monitor"):
                gr.Markdown("*Admin only — shows live service health*")
                refresh_btn = gr.Button("Refresh Status", variant="secondary")
                status_output = gr.Markdown()
                refresh_btn.click(refresh_system_status, inputs=[token_box], outputs=status_output)

    return app


def main() -> None:
    """Entry point for running the Gradio app standalone."""
    import os
    api_base = os.environ.get("CHIPWISE_API_URL", "http://localhost:8080")
    app = create_gradio_app(api_base)
    if app is None:
        print("ERROR: gradio not installed. Run: pip install gradio")
        return
    app.launch(server_port=7860, share=False)


if __name__ == "__main__":
    main()
