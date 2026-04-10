#!/usr/bin/env python3
"""QA Config — Switch settings.yaml profiles for testing ChipWise Enterprise configurations.

Usage:
    python .github/skills/qa-tester/scripts/qa_config.py show          # List profiles
    python .github/skills/qa-tester/scripts/qa_config.py check         # Verify current config
    python .github/skills/qa-tester/scripts/qa_config.py apply <name>  # Apply a profile
    python .github/skills/qa-tester/scripts/qa_config.py restore       # Restore backup

Profiles:
    default            Restore standard LM Studio config (primary + router)
    small_model        Primary LLM → smaller model for speed testing
    no_reranker        Disable bce-reranker (reranker.enabled=false)
    no_cache           Disable GPTCache (cache.enabled=false)
    invalid_llm        LLM base_url → unreachable endpoint
    invalid_embed      Embedding base_url → unreachable endpoint
    high_concurrency   Raise rate limits + agent.max_iterations
"""

import argparse
import shutil
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("ERROR: PyYAML is required. Install with: pip install pyyaml")
    sys.exit(2)

REPO_ROOT = Path(__file__).resolve().parents[4]
SETTINGS_FILE = REPO_ROOT / "config" / "settings.yaml"
SETTINGS_BACKUP = REPO_ROOT / "config" / "settings.yaml.bak"


def _load_yaml(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _save_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.dump(data, default_flow_style=False, allow_unicode=True), encoding="utf-8")


def _backup() -> None:
    """Create backup if not already backed up."""
    if not SETTINGS_BACKUP.exists():
        shutil.copy2(SETTINGS_FILE, SETTINGS_BACKUP)
        print(f"   📋 Backup created: {SETTINGS_BACKUP.name}")
    else:
        print(f"   📋 Backup already exists")


def _ensure_section(settings: dict, *keys) -> dict:
    """Ensure nested dict path exists."""
    d = settings
    for k in keys:
        if k not in d or not isinstance(d[k], dict):
            d[k] = {}
        d = d[k]
    return d


# ── Profile Mutators ─────────────────────────────────────────────────────

def apply_default(settings: dict) -> dict:
    """Restore standard LM Studio config (primary qwen3-35b + router qwen3-1.7b)."""
    llm = _ensure_section(settings, "llm")
    primary = _ensure_section(settings, "llm", "primary")
    primary["provider"] = "openai_compatible"
    primary["base_url"] = "http://localhost:1234/v1"
    primary["model"] = "qwen3-35b-q5_k_m"
    primary["api_key"] = "lm-studio"

    router = _ensure_section(settings, "llm", "router")
    router["provider"] = "openai_compatible"
    router["base_url"] = "http://localhost:1234/v1"
    router["model"] = "qwen3-1.7b-q5_k_m"
    router["api_key"] = "lm-studio"

    print("   LLM primary -> qwen3-35b-q5_k_m (localhost:1234)")
    print("   LLM router  -> qwen3-1.7b-q5_k_m (localhost:1234)")
    return settings


def apply_small_model(settings: dict) -> dict:
    """Switch primary LLM to a smaller model for speed testing."""
    primary = _ensure_section(settings, "llm", "primary")
    primary["model"] = "qwen3-8b-q5_k_m"
    print("   LLM primary -> qwen3-8b-q5_k_m (smaller model)")
    return settings


def apply_no_reranker(settings: dict) -> dict:
    """Disable bce-reranker."""
    reranker = _ensure_section(settings, "reranker")
    reranker["enabled"] = False
    print("   Reranker -> disabled")
    return settings


def apply_no_cache(settings: dict) -> dict:
    """Disable GPTCache."""
    cache = _ensure_section(settings, "cache")
    cache["enabled"] = False
    print("   Cache -> disabled")
    return settings


def apply_invalid_llm(settings: dict) -> dict:
    """Set LLM base_url to unreachable endpoint."""
    primary = _ensure_section(settings, "llm", "primary")
    primary["base_url"] = "http://localhost:9999/v1"
    print("   LLM primary base_url -> http://localhost:9999/v1 (unreachable)")
    return settings


def apply_invalid_embed(settings: dict) -> dict:
    """Set embedding base_url to unreachable endpoint."""
    embedding = _ensure_section(settings, "embedding")
    embedding["base_url"] = "http://localhost:9999"
    print("   Embedding base_url -> http://localhost:9999 (unreachable)")
    return settings


def apply_high_concurrency(settings: dict) -> dict:
    """Raise rate limits and agent iterations for stress testing."""
    rate_limit = _ensure_section(settings, "rate_limit")
    rate_limit["per_user_per_minute"] = 100
    rate_limit["per_user_per_hour"] = 2000

    agent = _ensure_section(settings, "agent")
    agent["max_iterations"] = 10

    print("   Rate limit -> 100/min, 2000/hr")
    print("   Agent max_iterations -> 10")
    return settings


PROFILES = {
    "default": apply_default,
    "small_model": apply_small_model,
    "no_reranker": apply_no_reranker,
    "no_cache": apply_no_cache,
    "invalid_llm": apply_invalid_llm,
    "invalid_embed": apply_invalid_embed,
    "high_concurrency": apply_high_concurrency,
}


# ── Commands ─────────────────────────────────────────────────────────────

def cmd_show() -> None:
    """Show available profiles."""
    print("📋 Available Configuration Profiles")
    print("=" * 55)
    for name, fn in PROFILES.items():
        doc = fn.__doc__ or ""
        print(f"   {name:20s} {doc.strip()}")
    print()
    print(f"Settings file: {SETTINGS_FILE}")
    print(f"Backup exists: {SETTINGS_BACKUP.exists()}")


def cmd_check() -> None:
    """Check current configuration."""
    print("🔧 Current Configuration")
    print("=" * 55)

    if not SETTINGS_FILE.exists():
        print(f"   ❌ {SETTINGS_FILE} not found")
        return

    settings = _load_yaml(SETTINGS_FILE)

    # LLM config
    llm = settings.get("llm", {})
    primary = llm.get("primary", {})
    router = llm.get("router", {})
    print(f"   LLM primary:  {primary.get('model', '(not set)')} @ {primary.get('base_url', '(not set)')}")
    print(f"   LLM router:   {router.get('model', '(not set)')} @ {router.get('base_url', '(not set)')}")

    # Embedding
    embedding = settings.get("embedding", {})
    print(f"   Embedding:    {embedding.get('provider', '(not set)')} @ {embedding.get('base_url', '(not set)')}")

    # Reranker
    reranker = settings.get("reranker", {})
    print(f"   Reranker:     enabled={reranker.get('enabled', '(not set)')}")

    # Cache
    cache = settings.get("cache", {})
    print(f"   Cache:        enabled={cache.get('enabled', '(not set)')}")

    # Rate limit
    rl = settings.get("rate_limit", {})
    print(f"   Rate limit:   {rl.get('per_user_per_minute', '?')}/min, {rl.get('per_user_per_hour', '?')}/hr")

    # Agent
    agent = settings.get("agent", {})
    print(f"   Agent:        max_iterations={agent.get('max_iterations', '?')}")

    print(f"\n   Backup: {'exists' if SETTINGS_BACKUP.exists() else 'none'}")


def cmd_apply(profile_name: str) -> None:
    """Apply a configuration profile."""
    if profile_name not in PROFILES:
        print(f"❌ Unknown profile: {profile_name}")
        print(f"   Available: {', '.join(PROFILES.keys())}")
        sys.exit(1)

    if not SETTINGS_FILE.exists():
        print(f"❌ {SETTINGS_FILE} not found — create it first (Phase 1A task)")
        sys.exit(1)

    print(f"🔄 Applying profile: {profile_name}")
    _backup()

    settings = _load_yaml(SETTINGS_FILE)
    settings = PROFILES[profile_name](settings)
    _save_yaml(SETTINGS_FILE, settings)
    print(f"   ✅ settings.yaml updated")


def cmd_restore() -> None:
    """Restore settings.yaml from backup."""
    if not SETTINGS_BACKUP.exists():
        print("❌ No backup found. Nothing to restore.")
        return

    shutil.copy2(SETTINGS_BACKUP, SETTINGS_FILE)
    SETTINGS_BACKUP.unlink()
    print("✅ settings.yaml restored from backup")


def main() -> None:
    parser = argparse.ArgumentParser(description="QA Config — manage ChipWise settings profiles")
    parser.add_argument(
        "command",
        choices=["show", "check", "apply", "restore"],
        help="Command to execute",
    )
    parser.add_argument(
        "profile",
        nargs="?",
        help="Profile name (for 'apply' command)",
    )
    args = parser.parse_args()

    if args.command == "show":
        cmd_show()
    elif args.command == "check":
        cmd_check()
    elif args.command == "apply":
        if not args.profile:
            print("❌ Profile name required. Usage: qa_config.py apply <profile>")
            sys.exit(1)
        cmd_apply(args.profile)
    elif args.command == "restore":
        cmd_restore()


if __name__ == "__main__":
    main()
