# Contributing to ChipWise Enterprise

Thank you for contributing! This guide covers everything you need to get started.

## Development Environment Setup

See [docs/LOCAL_DEVELOPMENT.md](docs/LOCAL_DEVELOPMENT.md) for full setup instructions.

**Quick version:**
```bash
git clone <repo-url> && cd ChipWise-Enterprise
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
docker-compose up -d postgres redis milvus
alembic upgrade head && python scripts/init_milvus.py && python scripts/init_kuzu.py

# Install pre-commit hooks
pip install pre-commit
pre-commit install
pre-commit install --hook-type pre-push
```

## Branch Strategy

| Branch | Purpose |
|--------|---------|
| `main` | Production-ready code. Protected — requires PR + review. |
| `develop` | Integration branch. PRs merge here first. |
| `feature/<name>` | New features. Branch from `develop`. |
| `fix/<name>` | Bug fixes. Branch from `develop` (or `main` for hotfixes). |

## Commit Convention

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer(s)]
```

**Types:** `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `perf`, `ci`
**Scopes:** `api`, `agent`, `core`, `libs`, `ingestion`, `auth`, `frontend`, `infra`

Examples:
```
feat(agent): add chip_select tool for parametric filtering
fix(api): handle 503 when LM Studio is unreachable
docs(arch): update Milvus hybrid search diagram
test(core): add QueryRewriter edge case coverage
```

## Pull Request Process

1. Create a feature/fix branch from `develop`
2. Make changes, ensuring all checks pass locally
3. Push and open a PR using the PR template
4. Request review from at least one team member
5. Address review comments
6. Squash-merge into `develop`

### PR Checklist (from template)

- [ ] `ruff check` and `mypy` clean
- [ ] `pytest -m unit` green
- [ ] `pytest -m integration_nollm` green (if touching integration paths)
- [ ] `npm run build && npm run test:run` green (if touching frontend)
- [ ] Manual verification steps documented

## Testing Requirements

### For every PR:
- **Unit tests required** for new logic (`tests/unit/`)
- Tests must be independent of Docker or LM Studio (use mocks)
- Use `@pytest.mark.unit` marker

### Preferred additions:
- **integration_nollm** tests (`tests/integration/`) — requires only PG/Redis/Milvus
- These run in CI with GitHub Actions service containers

### Markers:
```python
@pytest.mark.unit           # No external deps
@pytest.mark.integration    # Full Docker infra + LM Studio
@pytest.mark.integration_nollm  # Docker infra only (no LM Studio)
@pytest.mark.e2e            # Full system running
@pytest.mark.load           # Performance tests (Locust)
```

## Code Style

- **Python**: Enforced by ruff (line-length 120, rules: E/F/W/I/N/UP/B/A/SIM) and mypy
- **TypeScript/Vue**: Enforced by `npm run build` (strict TypeScript)
- **Pre-commit hooks** run automatically — see `.pre-commit-config.yaml`

### Key patterns:
- Factory + pluggable abstractions in `src/libs/`
- Data contracts in `src/core/types.py` — extend, never break
- Agent tools inherit `BaseTool` in `src/agent/tools/`
- Configuration in `config/settings.yaml` — never hardcode
- LLM prompts in `config/prompts/*.txt` — never inline

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for diagrams and design decisions.

## Questions?

Open an issue or discuss in the team channel. For security issues, please follow responsible disclosure — do NOT open public issues for vulnerabilities.
