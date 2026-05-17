"""02_download_true_data.py — Download the K8s "true" (signal) corpus.

Strategy A (primary):
    Clone https://github.com/FareedKhan-dev/scalable-rag-pipeline and copy its
    `true_data/` directory into seed/docs/true_data/.

Strategy B (fallback — auto-used if strategy A fails or produces < 10 files):
    Scrape the kubernetes.io docs pages listed in config.yaml, render each to
    a clean plain-text file, and save as .txt in seed/docs/true_data/.  A very
    lightweight fetch (no JS rendering required — k8s docs are server-rendered).

This script is **idempotent**: already-downloaded files are not re-fetched
unless --force is passed.

Usage:
    uv run python scripts/data_pipeline/02_download_true_data.py
    uv run python scripts/data_pipeline/02_download_true_data.py --strategy b
    uv run python scripts/data_pipeline/02_download_true_data.py --force
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
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


def log(msg: str, *, indent: int = 0) -> None:
    prefix = "  " * indent
    print(f"[02_true] {prefix}{msg}", flush=True)


def human_size(total_bytes: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if total_bytes < 1024:
            return f"{total_bytes:.1f} {unit}"
        total_bytes /= 1024  # type: ignore[assignment]
    return f"{total_bytes:.1f} TB"


# ---------------------------------------------------------------------------
# Strategy A: clone FareedKhan-dev/scalable-rag-pipeline
# ---------------------------------------------------------------------------

def strategy_a(cfg: dict, out_dir: Path, temp_base: Path) -> int:
    """Clone the reference repo and copy its true_data/ folder.

    Returns the number of files copied (0 on failure).
    """
    repo_url: str = cfg["sources"]["true_repo_primary"]
    subdir: str = cfg["sources"]["true_repo_subdir"]
    clone_dest = temp_base / "fareed_rag_pipeline"

    log(f"Strategy A: cloning {repo_url}")
    if not clone_dest.exists():
        t0 = time.time()
        result = subprocess.run(
            ["git", "clone", "--depth", "1", "--no-tags", repo_url, str(clone_dest)],
            capture_output=True,
            text=True,
        )
        elapsed = time.time() - t0
        if result.returncode != 0:
            log(f"  git clone failed after {elapsed:.1f}s — falling back to Strategy B")
            log(f"  stderr: {result.stderr[:200]}", indent=1)
            return 0
        log(f"  Clone complete in {elapsed:.1f}s")
    else:
        log(f"  Clone already exists at {clone_dest}")

    src_dir = clone_dest / subdir
    if not src_dir.exists():
        log(f"  Sub-directory '{subdir}' not found in clone — falling back to Strategy B")
        # Clean up partial clone
        shutil.rmtree(clone_dest, ignore_errors=True)
        return 0

    # Copy all files from true_data/ into out_dir
    copied = 0
    for src_file in src_dir.rglob("*"):
        if not src_file.is_file():
            continue
        dest = out_dir / src_file.name
        if dest.exists():
            path_hash = hex(abs(hash(str(src_file))))[-6:]
            dest = out_dir / f"{path_hash}_{src_file.name}"
        try:
            shutil.copy2(src_file, dest)
            copied += 1
        except OSError as exc:
            log(f"  SKIP {src_file.name}: {exc}", indent=1)

    # Clean up clone to free disk
    log(f"  Copied {copied} files; removing clone")
    shutil.rmtree(clone_dest, ignore_errors=True)
    return copied


# ---------------------------------------------------------------------------
# Strategy B: scrape kubernetes.io
# ---------------------------------------------------------------------------

# Tags whose content we strip entirely (scripts, nav, etc.)
_STRIP_TAGS = re.compile(
    r"<(script|style|nav|header|footer|aside|noscript)[^>]*>.*?</\1>",
    re.DOTALL | re.IGNORECASE,
)
# All remaining HTML tags
_ALL_TAGS = re.compile(r"<[^>]+>")
# Consecutive blank lines → single blank line
_MULTI_BLANK = re.compile(r"\n{3,}")
# HTML entities
_ENTITIES = {
    "&amp;": "&",
    "&lt;": "<",
    "&gt;": ">",
    "&quot;": '"',
    "&#39;": "'",
    "&nbsp;": " ",
    "&#x27;": "'",
    "&mdash;": "—",
    "&ndash;": "–",
    "&hellip;": "…",
}


def _html_to_text(html: str) -> str:
    """Minimal HTML → plain-text conversion (no external deps)."""
    text = _STRIP_TAGS.sub("", html)
    text = _ALL_TAGS.sub("", text)
    for entity, char in _ENTITIES.items():
        text = text.replace(entity, char)
    # Decode numeric entities (basic pass)
    text = re.sub(r"&#(\d+);", lambda m: chr(int(m.group(1))), text)
    text = _MULTI_BLANK.sub("\n\n", text)
    return text.strip()


def _fetch_page(url: str, timeout: int = 30) -> str | None:
    """Fetch a URL and return the response body as text, or None on error."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (compatible; ADV-RAG-pipeline/1.0; "
                    "+https://github.com/FareedKhan-dev/scalable-rag-pipeline)"
                ),
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (urllib.error.URLError, OSError) as exc:
        log(f"    fetch error for {url}: {exc}", indent=2)
        return None


def strategy_b(cfg: dict, out_dir: Path) -> int:
    """Scrape kubernetes.io docs pages defined in config.yaml.

    Returns the number of files written.
    """
    base_url: str = cfg["sources"]["true_k8s_base_url"]
    pages: list[str] = cfg["sources"]["true_k8s_pages"]
    true_count: int = cfg["corpus"]["true_count"]

    log(f"Strategy B: scraping {len(pages)} pages from {base_url}")

    # Cap to configured true_count
    pages_to_fetch = pages[:true_count]
    written = 0

    for i, slug in enumerate(pages_to_fetch, start=1):
        url = urllib.parse.urljoin(base_url, slug)
        log(f"  [{i:02d}/{len(pages_to_fetch)}] {slug}", indent=1)

        html = _fetch_page(url)
        if html is None:
            log(f"    SKIP (fetch failed)", indent=2)
            continue

        text = _html_to_text(html)
        if len(text) < 200:
            log(f"    SKIP (page too short after stripping: {len(text)} chars)", indent=2)
            continue

        # Derive a filesystem-safe filename from the slug
        safe_name = slug.strip("/").replace("/", "__").replace(" ", "_")
        out_file = out_dir / f"{safe_name}.txt"

        out_file.write_text(text, encoding="utf-8")
        written += 1

        # Polite crawl delay — avoid hammering kubernetes.io
        time.sleep(0.5)

    log(f"  Scraped and saved {written} pages")
    return written


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Download the K8s true corpus")
    parser.add_argument(
        "--strategy",
        choices=["a", "b", "auto"],
        default="auto",
        help="a=clone fareed repo, b=scrape k8s.io, auto=try a then fall back to b",
    )
    parser.add_argument("--force", action="store_true",
                        help="Re-download even if output dir is non-empty")
    args = parser.parse_args()

    cfg = load_config()
    out_dir = PROJECT_ROOT / cfg["output"]["true_data_dir"]
    temp_base = Path(cfg["output"]["temp_clone_dir"])

    out_dir.mkdir(parents=True, exist_ok=True)
    temp_base.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Idempotency check — ignore .gitkeep so the empty-dir sentinel does
    # not get counted as "already populated".
    # ------------------------------------------------------------------
    existing = [p for p in out_dir.iterdir() if p.is_file() and p.name != ".gitkeep"]
    if existing and not args.force:
        log(f"Output dir already contains {len(existing)} files; use --force to re-run")
        log(f"  → {out_dir}")
        _print_summary(out_dir)
        return

    log("=" * 60)
    log("ADV RAG — Step 02: Download True (K8s) Corpus")
    log("=" * 60)
    log(f"Output: {out_dir}")

    # ------------------------------------------------------------------
    # Execute chosen strategy
    # ------------------------------------------------------------------
    file_count = 0

    if args.strategy in ("a", "auto"):
        file_count = strategy_a(cfg, out_dir, temp_base)
        if file_count < 10 and args.strategy == "auto":
            log(f"Strategy A yielded only {file_count} files — switching to Strategy B")
            file_count = strategy_b(cfg, out_dir)

    elif args.strategy == "b":
        file_count = strategy_b(cfg, out_dir)

    # ------------------------------------------------------------------
    # Final check
    # ------------------------------------------------------------------
    if file_count == 0:
        log("ERROR: Both strategies produced 0 files. Check network connectivity.")
        sys.exit(1)

    _print_summary(out_dir)


def _print_summary(out_dir: Path) -> None:
    files = [p for p in out_dir.iterdir() if p.is_file() and p.name != ".gitkeep"]
    total_bytes = sum(p.stat().st_size for p in files)
    ext_counts: dict[str, int] = {}
    for p in files:
        ext_counts[p.suffix.lower()] = ext_counts.get(p.suffix.lower(), 0) + 1

    log("")
    log("─" * 50)
    log("TRUE CORPUS SUMMARY")
    log("─" * 50)
    log(f"  Directory : {out_dir}")
    log(f"  File count: {len(files)}")
    log(f"  Total size: {human_size(total_bytes)}")
    for ext, count in sorted(ext_counts.items(), key=lambda x: -x[1]):
        log(f"    {ext or '(no ext)':>8} : {count}", indent=1)
    log("─" * 50)


if __name__ == "__main__":
    main()
