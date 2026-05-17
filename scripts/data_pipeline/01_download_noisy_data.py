"""01_download_noisy_data.py — Download and sample the noisy corpus.

Clones the tpn/pdfs repository to a temp directory, walks the entire tree to
find files matching the configured extensions, randomly samples `noise_count`
of them (fixed seed for reproducibility), and copies them into
seed/docs/noisy_data/.

This script is **idempotent**: files already present are not re-downloaded
unless --force is passed.  The clone is removed after sampling to reclaim
disk space (unless --keep-clone is passed for debugging).

Usage:
    uv run python scripts/data_pipeline/01_download_noisy_data.py
    uv run python scripts/data_pipeline/01_download_noisy_data.py --force
    uv run python scripts/data_pipeline/01_download_noisy_data.py --keep-clone
"""

from __future__ import annotations

import argparse
import random
import shutil
import subprocess
import sys
import time
from pathlib import Path

import yaml  # PyYAML is a transitive dep of many packages already in the venv

# ---------------------------------------------------------------------------
# Resolve paths relative to project root (two levels up from this script)
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
CONFIG_PATH = SCRIPT_DIR / "config.yaml"


def load_config() -> dict:
    with open(CONFIG_PATH) as fh:
        return yaml.safe_load(fh)


def log(msg: str, *, indent: int = 0) -> None:
    prefix = "  " * indent
    print(f"[01_noisy] {prefix}{msg}", flush=True)


# ---------------------------------------------------------------------------
# Core helpers
# ---------------------------------------------------------------------------

def clone_repo(url: str, dest: Path) -> None:
    """Shallow-clone *url* into *dest* (depth=1 to minimise download size)."""
    if dest.exists():
        log(f"Clone already exists at {dest}, skipping git clone")
        return
    log(f"Cloning {url}")
    log(f"  → dest: {dest}")
    log("  (shallow clone — this may take several minutes on first run)")
    t0 = time.time()
    result = subprocess.run(
        ["git", "clone", "--depth", "1", "--no-tags", url, str(dest)],
        capture_output=True,
        text=True,
    )
    elapsed = time.time() - t0
    if result.returncode != 0:
        log(f"ERROR: git clone failed after {elapsed:.1f}s")
        log(result.stderr, indent=1)
        sys.exit(1)
    log(f"Clone complete in {elapsed:.1f}s")


def discover_files(root: Path, allowed_exts: set[str], min_bytes: int, max_bytes: int) -> list[Path]:
    """Walk *root* recursively and return all files matching the filter criteria."""
    log(f"Scanning {root} for eligible files …")
    candidates: list[Path] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in allowed_exts:
            continue
        try:
            size = path.stat().st_size
        except OSError:
            continue
        if size < min_bytes or size > max_bytes:
            continue
        candidates.append(path)
    log(f"Found {len(candidates):,} eligible files in the clone")
    return candidates


def human_size(total_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if total_bytes < 1024:
            return f"{total_bytes:.1f} {unit}"
        total_bytes /= 1024  # type: ignore[assignment]
    return f"{total_bytes:.1f} TB"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Download + sample the noisy corpus")
    parser.add_argument("--force", action="store_true",
                        help="Re-copy files even if output dir is non-empty")
    parser.add_argument("--keep-clone", action="store_true",
                        help="Do not remove the temp clone after sampling")
    args = parser.parse_args()

    cfg = load_config()

    noise_count: int = cfg["corpus"]["noise_count"]
    # Hard size ceiling (MB) for the noisy corpus — stops sampling once hit.
    # Falls back to a generous default if the key is missing from config.
    max_total_mb: int = int(cfg["corpus"].get("noise_max_total_mb", 800))
    max_total_bytes: int = max_total_mb * 1024 * 1024
    seed: int = cfg["corpus"]["random_seed"]
    repo_url: str = cfg["sources"]["noisy_repo"]
    allowed_exts = {ext.lower() for ext in cfg["filters"]["allowed_extensions"]}
    min_bytes: int = cfg["filters"]["min_file_size_bytes"]
    max_bytes: int = cfg["filters"]["max_file_size_bytes"]
    temp_base = Path(cfg["output"]["temp_clone_dir"])
    out_dir = PROJECT_ROOT / cfg["output"]["noisy_data_dir"]

    # ------------------------------------------------------------------
    # Idempotency check — ignore .gitkeep so the empty-dir sentinel does
    # not get counted as "already populated".
    # ------------------------------------------------------------------
    out_dir.mkdir(parents=True, exist_ok=True)
    existing = [p for p in out_dir.iterdir() if p.is_file() and p.name != ".gitkeep"]
    if existing and not args.force:
        log(f"Output dir already contains {len(existing)} files; use --force to re-run")
        log(f"  → {out_dir}")
        _print_summary(out_dir)
        return

    log("=" * 60)
    log("ADV RAG — Step 01: Download Noisy Corpus")
    log("=" * 60)
    log(f"Target: {noise_count} files (or {max_total_mb} MB, whichever hits first)")
    log(f"Seed  : {seed}")
    log(f"Output: {out_dir}")

    # ------------------------------------------------------------------
    # Clone
    # ------------------------------------------------------------------
    clone_dest = temp_base / "tpn_pdfs"
    temp_base.mkdir(parents=True, exist_ok=True)
    clone_repo(repo_url, clone_dest)

    # ------------------------------------------------------------------
    # Discover + shuffle (full shuffle, not pre-sliced — so we can keep
    # pulling more candidates if the budget allows after rejecting any).
    # ------------------------------------------------------------------
    candidates = discover_files(clone_dest, allowed_exts, min_bytes, max_bytes)

    if not candidates:
        log("ERROR: no eligible files found in clone; aborting")
        sys.exit(1)

    rng = random.Random(seed)
    rng.shuffle(candidates)
    log(f"Shuffled {len(candidates):,} candidates (random seed={seed})")

    # ------------------------------------------------------------------
    # Greedy copy with TWO stopping conditions:
    #   1. file count reaches `noise_count`
    #   2. cumulative size reaches `max_total_bytes`
    # ------------------------------------------------------------------
    log(f"Copying files → {out_dir}")
    log(f"  Stop conditions: count >= {noise_count}  OR  size >= {max_total_mb} MB")

    copied = 0
    skipped = 0
    cumulative_bytes = 0

    for src in candidates:
        # Budget exhausted?
        if copied >= noise_count:
            break
        try:
            src_size = src.stat().st_size
        except OSError:
            skipped += 1
            continue
        if cumulative_bytes + src_size > max_total_bytes:
            # Skip files that would overflow the cap. We keep iterating to
            # try to fit smaller ones in the remaining headroom.
            continue

        # Flatten all files into the output dir; disambiguate name collisions
        # by appending a short hash of the source path.
        dest = out_dir / src.name
        if dest.exists():
            path_hash = hex(abs(hash(str(src))))[-6:]
            dest = out_dir / f"{path_hash}_{src.name}"

        try:
            shutil.copy2(src, dest)
            copied += 1
            cumulative_bytes += src_size
        except OSError as exc:
            log(f"  SKIP {src.name}: {exc}", indent=1)
            skipped += 1

        if copied % 100 == 0 and copied > 0:
            log(
                f"  … {copied}/{noise_count} files, "
                f"{human_size(cumulative_bytes)} / {max_total_mb} MB",
                indent=1,
            )

    log(
        f"Copy complete: {copied} files, "
        f"{human_size(cumulative_bytes)} total, {skipped} skipped"
    )
    if copied < noise_count and cumulative_bytes >= max_total_bytes * 0.95:
        log(
            f"  (Size budget of {max_total_mb} MB hit before reaching "
            f"{noise_count} files — this is expected.)"
        )

    # ------------------------------------------------------------------
    # Clean up clone (unless --keep-clone)
    # ------------------------------------------------------------------
    if not args.keep_clone:
        log(f"Removing temp clone: {clone_dest}")
        shutil.rmtree(clone_dest, ignore_errors=True)
    else:
        log(f"Keeping temp clone at: {clone_dest} (--keep-clone)")

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    _print_summary(out_dir)


def _print_summary(out_dir: Path) -> None:
    files = [p for p in out_dir.iterdir() if p.is_file() and p.name != ".gitkeep"]
    total_bytes = sum(p.stat().st_size for p in files)
    ext_counts: dict[str, int] = {}
    for p in files:
        ext_counts[p.suffix.lower()] = ext_counts.get(p.suffix.lower(), 0) + 1

    log("")
    log("─" * 50)
    log("NOISY CORPUS SUMMARY")
    log("─" * 50)
    log(f"  Directory : {out_dir}")
    log(f"  File count: {len(files)}")
    log(f"  Total size: {human_size(total_bytes)}")
    for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1]):
        log(f"    {ext or '(no ext)':>8} : {count}", indent=1)
    log("─" * 50)


if __name__ == "__main__":
    main()
