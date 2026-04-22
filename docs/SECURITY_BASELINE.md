# Security Baseline Report

**Date**: 2026-04-14
**Scanned by**: bandit (Python SAST), pip-audit (Python deps), npm audit (frontend deps)

## Summary

| Tool | Total Findings | HIGH/CRITICAL | Status |
|------|---------------|---------------|--------|
| Bandit (Python SAST) | 21 | 1 HIGH | Reviewed ✅ |
| pip-audit (Python deps) | 0 | 0 | Clean ✅ |
| npm audit (frontend deps) | 0 | 0 | Clean ✅ |

## Bandit Findings Breakdown

- **High severity**: 1 — MD5 hash usage in `src/cache/semantic_cache.py:47` (B324/CWE-327)
- **Medium severity**: 1
- **Low severity**: 19 (mostly `try-except-pass` patterns, subprocess usage with controlled input)

### Accepted Risks

| Finding | Location | Justification |
|---------|----------|---------------|
| B324: MD5 usage | `src/cache/semantic_cache.py:47` | Used for cache key fingerprinting only (non-cryptographic). SimHash locality-sensitive hashing — collision is acceptable for cache eviction. NOT used for passwords, signatures, or integrity checks. |

### CI Gate Policy

- **bandit**: `bandit -r src -lll -iii` — only fails on HIGH severity + HIGH confidence issues
- **pip-audit**: fails on any known vulnerability
- **npm audit**: `npm audit --audit-level=high` — fails on HIGH+ severity

## Dependency Health

- **Python**: All 17+ direct dependencies clear of known CVEs
- **Frontend**: All npm packages clear of known vulnerabilities
- **Transitive**: No actionable transitive dependency vulnerabilities found

## Upgrade Path

1. Monitor GitHub Dependabot alerts (enabled via security-scan.yaml weekly schedule)
2. Quarterly manual review of this baseline
3. For new HIGH findings: fix within 7 days or document exception with team approval
