"""04_validate_dataset.py — Validate the assembled dataset before ingestion.

Checks:
  1. File counts and sizes in seed/docs/true_data/
  2. File counts and sizes in seed/docs/noisy_data/
  3. Existence and parse-ability of seed/migrations/003_seed_k8s_ops.sql
  4. Prints a consolidated summary table

Exit codes:
  0 — all checks pass (within tolerances)
  1 — one or more hard failures

Usage:
    uv run python scripts/data_pipeline/04_validate_dataset.py
    uv run python scripts/data_pipeline/04_validate_dataset.py --strict
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
CONFIG_PATH = SCRIPT_DIR / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH) as fh:
        return yaml.safe_load(fh)


def human_size(total_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if total_bytes < 1024:
            return f"{total_bytes:.1f} {unit}"
        total_bytes /= 1024  # type: ignore[assignment]
    return f"{total_bytes:.1f} TB"


PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"


def _status_icon(status: str) -> str:
    return {"PASS": "✓", "WARN": "~", "FAIL": "✗"}.get(status, "?")


# ---------------------------------------------------------------------------
# Check functions
# ---------------------------------------------------------------------------

CheckResult = tuple[str, str, str]  # (label, detail, status)


def check_directory(
    label: str,
    dir_path: Path,
    expected_count: int,
    *,
    expected_size_mb: int | None = None,
    tolerance: float = 0.5,   # allow 50 % below expected count before FAIL
    warn_fraction: float = 0.8,
) -> CheckResult:
    """Check a directory's file count and total size.

    A directory passes if EITHER the file count OR the total size meets the
    expected threshold — this accommodates the noisy corpus which stops
    sampling early when its size budget is hit (often before reaching the
    target file count).
    """
    if not dir_path.exists():
        return label, "directory missing", FAIL

    # Ignore .gitkeep sentinel files — they are not real corpus content.
    files = [p for p in dir_path.iterdir() if p.is_file() and p.name != ".gitkeep"]
    count = len(files)
    total_bytes = sum(p.stat().st_size for p in files)
    total_mb = total_bytes / (1024 * 1024)
    size_str = human_size(total_bytes)
    detail = f"{count} files, {size_str}"

    if count == 0:
        return label, detail, FAIL

    # Pass if EITHER count OR size meets threshold
    count_ok_warn = count >= expected_count * warn_fraction
    count_ok_fail = count >= expected_count * tolerance
    size_ok_warn = (expected_size_mb is not None
                    and total_mb >= expected_size_mb * warn_fraction)
    size_ok_fail = (expected_size_mb is not None
                    and total_mb >= expected_size_mb * tolerance)

    if count_ok_warn or size_ok_warn:
        status = PASS
    elif count_ok_fail or size_ok_fail:
        status = WARN
    else:
        status = FAIL

    return label, detail, status


def check_sql_file(label: str, sql_path: Path, target_mb: int) -> CheckResult:
    """Verify the SQL migration file exists, is non-empty, and has expected structure."""
    if not sql_path.exists():
        return label, "file missing", FAIL

    size = sql_path.stat().st_size
    size_mb = size / (1024 * 1024)
    size_str = human_size(size)

    if size == 0:
        return label, f"file is empty (0 B)", FAIL

    # Basic SQL sanity check: verify expected tables are present
    try:
        # Read just enough to find CREATE TABLE statements
        content = sql_path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        return label, f"cannot read: {exc}", FAIL

    expected_tables = {
        "clusters", "nodes", "deployments", "pods",
        "incidents", "alerts", "oncall_logs",
    }
    found_tables = set(re.findall(r"CREATE TABLE\s+(\w+)", content, re.IGNORECASE))
    missing = expected_tables - found_tables
    if missing:
        return label, f"missing CREATE TABLE for: {missing}", FAIL

    # Count INSERT rows as a sanity check (approximate, via semicolons in INSERT blocks)
    insert_count = len(re.findall(r"^INSERT INTO", content, re.MULTILINE))
    detail = f"1 file, {size_str}, {insert_count} INSERT batches"

    if size_mb < target_mb * 0.4:
        status = WARN  # much smaller than expected but not empty
        detail += f" (WARNING: expected ~{target_mb} MB)"
    else:
        status = PASS

    return label, detail, status


def check_noise_ratio(
    true_count: int,
    noisy_count: int,
    expected_noise: int,
    expected_true: int,
) -> CheckResult:
    """Verify the 95/5 noise-to-signal ratio."""
    total = true_count + noisy_count
    if total == 0:
        return "noise ratio", "no files found", FAIL
    actual_noise_pct = noisy_count / total * 100
    expected_noise_pct = expected_noise / (expected_noise + expected_true) * 100
    detail = (
        f"{actual_noise_pct:.1f}% noise "
        f"({noisy_count} noisy / {true_count} true / {total} total), "
        f"target={expected_noise_pct:.0f}%"
    )
    # Allow ±10 pp deviation before warning
    if abs(actual_noise_pct - expected_noise_pct) > 10:
        status = WARN
    else:
        status = PASS
    return "noise ratio", detail, status


# ---------------------------------------------------------------------------
# Summary table
# ---------------------------------------------------------------------------

def print_summary(results: list[CheckResult], totals: dict) -> None:
    print()
    print("=" * 64)
    print("  ADV RAG — Dataset Validation Report")
    print("=" * 64)

    # Individual checks
    print(f"  {'Component':<20} {'Detail':<32} {'Status'}")
    print("  " + "─" * 60)
    for label, detail, status in results:
        icon = _status_icon(status)
        print(f"  {label:<20} {detail:<32} {icon} {status}")

    # Totals box
    print()
    print("  " + "─" * 60)
    print(f"  {'true_data:':<20} {totals.get('true_count', 0):>5} files,  {human_size(totals.get('true_bytes', 0)):>10}")
    print(f"  {'noisy_data:':<20} {totals.get('noisy_count', 0):>5} files,  {human_size(totals.get('noisy_bytes', 0)):>10}")
    print(f"  {'k8s_ops_db:':<20} {'1' if totals.get('sql_exists') else '0':>5} file,   {human_size(totals.get('sql_bytes', 0)):>10}")
    print("  " + "─" * 60)
    total_files = totals.get("true_count", 0) + totals.get("noisy_count", 0) + (1 if totals.get("sql_exists") else 0)
    total_bytes = totals.get("true_bytes", 0) + totals.get("noisy_bytes", 0) + totals.get("sql_bytes", 0)
    print(f"  {'TOTAL:':<20} {total_files:>5} files,  {human_size(total_bytes):>10}")
    print("=" * 64)
    print()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Validate assembled dataset")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat WARN results as FAIL",
    )
    args = parser.parse_args()

    cfg = load_config()

    true_dir = PROJECT_ROOT / cfg["output"]["true_data_dir"]
    noisy_dir = PROJECT_ROOT / cfg["output"]["noisy_data_dir"]
    sql_path = PROJECT_ROOT / cfg["output"]["sql_migration"]
    expected_noise: int = cfg["corpus"]["noise_count"]
    expected_noise_mb: int = int(cfg["corpus"].get("noise_max_total_mb", 800))
    expected_true: int = cfg["corpus"]["true_count"]
    target_sql_mb: int = cfg["sql_generator"]["target_size_mb"]

    results: list[CheckResult] = []

    # Run checks. Note: noisy_data is allowed to pass on EITHER count or size,
    # because the sampler stops early when its size budget is hit.
    r_true = check_directory("true_data", true_dir, expected_true)
    r_noisy = check_directory(
        "noisy_data", noisy_dir, expected_noise,
        expected_size_mb=expected_noise_mb,
    )
    r_sql = check_sql_file("k8s_ops_db", sql_path, target_sql_mb)
    results.extend([r_true, r_noisy, r_sql])

    # Counts for ratio check — exclude .gitkeep sentinels
    def _real_files(d: Path) -> list[Path]:
        if not d.exists():
            return []
        return [p for p in d.iterdir() if p.is_file() and p.name != ".gitkeep"]

    true_files = _real_files(true_dir)
    noisy_files = _real_files(noisy_dir)
    true_count = len(true_files)
    noisy_count = len(noisy_files)
    r_ratio = check_noise_ratio(true_count, noisy_count, expected_noise, expected_true)
    results.append(r_ratio)

    # Totals
    true_bytes = sum(p.stat().st_size for p in true_files)
    noisy_bytes = sum(p.stat().st_size for p in noisy_files)
    sql_bytes = sql_path.stat().st_size if sql_path.exists() else 0

    totals = {
        "true_count": true_count,
        "noisy_count": noisy_count,
        "sql_exists": sql_path.exists(),
        "true_bytes": true_bytes,
        "noisy_bytes": noisy_bytes,
        "sql_bytes": sql_bytes,
    }

    print_summary(results, totals)

    # Exit code
    has_fail = any(status == FAIL for _, _, status in results)
    has_warn = any(status == WARN for _, _, status in results)

    if has_fail:
        print("RESULT: FAIL — one or more critical checks failed.")
        print("        Run the earlier pipeline steps and re-validate.")
        sys.exit(1)
    elif has_warn and args.strict:
        print("RESULT: FAIL — warnings found and --strict mode is active.")
        sys.exit(1)
    elif has_warn:
        print("RESULT: PASS (with warnings) — dataset usable but below ideal targets.")
        print("        Use --strict to treat warnings as failures.")
    else:
        print("RESULT: PASS — all checks passed. Dataset ready for ingestion.")


if __name__ == "__main__":
    main()
