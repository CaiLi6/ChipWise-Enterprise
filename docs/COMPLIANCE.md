# Compliance — License & SBOM Audit

**Date**: 2026-04-14

## Allowed License Whitelist

- MIT / MIT-CMU
- BSD (2-Clause, 3-Clause)
- Apache-2.0
- ISC
- PSF-2.0
- 0BSD / CC0-1.0 / Zlib (permissive)

## Non-Whitelist Dependencies

| Package | License | Risk | Action |
|---------|---------|------|--------|
| `certifi` | MPL-2.0 | Low | Widely used CA bundle; MPL-2.0 copyleft only applies to modified files of certifi itself. Accepted. |
| `chardet` | LGPLv2+ | Low | Character detection; LGPL allows dynamic linking without copyleft propagation. Used as-is. Accepted. |
| `fqdn` | MPL-2.0 | Low | Tiny utility; file-level copyleft only. Accepted. |
| `pathspec` | MPL-2.0 | Low | Gitignore pattern matching (dev tool); MPL-2.0 file-level copyleft. Accepted. |
| `psycopg2-binary` | LGPL | Low | Standard PostgreSQL adapter; LGPL allows dynamic linking. Industry-standard practice. Accepted. |

**No GPL (strong copyleft) dependencies found.** All non-whitelist licenses are weak copyleft (LGPL/MPL-2.0) — safe for proprietary use without code disclosure obligations.

## SBOM Files

| File | Description |
|------|-------------|
| `reports/sbom-python.json` | CycloneDX SBOM for Python dependencies |
| `reports/sbom-frontend.json` | CycloneDX SBOM for npm dependencies (generate via CI) |
| `reports/licenses-python.json` | pip-licenses output (JSON) |
| `reports/licenses-frontend.json` | license-checker output (generate via CI) |

## Recommendations

1. Pin transitive dependencies to prevent unexpected license changes
2. Re-run license audit quarterly or on major dependency updates
3. Consider replacing `chardet` with `charset-normalizer` (MIT) if LGPL is a concern
