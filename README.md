# ChipWise Enterprise

Chip data intelligence retrieval and analysis platform for semiconductor hardware teams.

Uses **Agentic RAG** (ReAct Agent + Tool Calling) and **Graph RAG** (Kuzu knowledge graph) for natural-language chip queries, comparisons, BOM review, and test case generation. All inference runs locally via LM Studio.

## Quick Start

```bash
# Infrastructure
docker-compose up -d

# Install dependencies
pip install -r requirements.txt

# Run API gateway
uvicorn src.api.main:app --host 0.0.0.0 --port 8080
```

See `CLAUDE.md` for full setup instructions and `docs/ENTERPRISE_DEV_SPEC.md` for architecture details.
