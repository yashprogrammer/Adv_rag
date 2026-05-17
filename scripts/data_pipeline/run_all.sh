#!/usr/bin/env bash
# =============================================================================
# run_all.sh — ADV RAG Data Pipeline Orchestrator
#
# Runs all five pipeline steps in order:
#   01 — Download noisy corpus (tpn/pdfs)
#   02 — Download true corpus (K8s docs)
#   03 — Generate K8s ops SQL seed data
#   05 — Diversify true-corpus formats (TXT → mix of PDF/DOCX/HTML/TXT)
#   04 — Validate assembled dataset
#
# Usage:
#   bash scripts/data_pipeline/run_all.sh
#   bash scripts/data_pipeline/run_all.sh --force        # re-download everything
#   bash scripts/data_pipeline/run_all.sh --skip-noise   # skip step 01 (already done)
#   bash scripts/data_pipeline/run_all.sh --skip-true    # skip step 02
#   bash scripts/data_pipeline/run_all.sh --fast-sql     # use tiny row counts in step 03
#   bash scripts/data_pipeline/run_all.sh --strict       # fail on warnings in step 04
#
# Prerequisites:
#   - uv installed (https://docs.astral.sh/uv/)
#   - ~5 GB free disk on /tmp for the temporary noise repo clone (deleted
#     after sampling). Final sampled corpus is capped at ~800 MB.
#   - Network access to github.com and kubernetes.io
#
# Exit behaviour:
#   Exits with code 1 immediately if any step fails (set -e).
# =============================================================================

set -euo pipefail

# ---------------------------------------------------------------------------
# Resolve script and project root directories
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------
FORCE=""
SKIP_NOISE=false
SKIP_TRUE=false
FAST_SQL=false
STRICT=""

for arg in "$@"; do
    case "$arg" in
        --force)       FORCE="--force" ;;
        --skip-noise)  SKIP_NOISE=true ;;
        --skip-true)   SKIP_TRUE=true ;;
        --fast-sql)    FAST_SQL=true ;;
        --strict)      STRICT="--strict" ;;
        --help|-h)
            grep '^#' "$0" | sed 's/^# \?//'
            exit 0
            ;;
        *)
            echo "Unknown argument: $arg" >&2
            echo "Run with --help for usage." >&2
            exit 1
            ;;
    esac
done

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
BOLD='\033[1m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
RESET='\033[0m'

banner() {
    echo ""
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo -e "${BOLD}  $1${RESET}"
    echo -e "${BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
    echo ""
}

step_ok() {
    echo -e "${GREEN}  ✓ $1 complete${RESET}"
    echo ""
}

step_skip() {
    echo -e "${YELLOW}  ~ $1 skipped${RESET}"
    echo ""
}

fatal() {
    echo -e "${RED}  ✗ FATAL: $1${RESET}" >&2
    exit 1
}

# ---------------------------------------------------------------------------
# Pre-flight checks
# ---------------------------------------------------------------------------
banner "ADV RAG — Data Pipeline"
echo "  Project root : $PROJECT_ROOT"
echo "  Started at   : $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
echo ""

# Verify uv is available
if ! command -v uv &>/dev/null; then
    fatal "uv not found. Install from https://docs.astral.sh/uv/ then re-run."
fi
echo "  uv version   : $(uv --version)"

# Check free disk space (need ~5 GB on /tmp for the temporary repo clone;
# the final sampled corpus is capped at ~800 MB by config.yaml).
if command -v df &>/dev/null; then
    FREE_KB=$(df -k /tmp 2>/dev/null | awk 'NR==2 {print $4}' || echo 0)
    FREE_GB=$((FREE_KB / 1048576))
    if [ "$FREE_GB" -lt 5 ]; then
        echo -e "${YELLOW}  WARNING: Only ~${FREE_GB} GB free on /tmp. The noise repo clone needs ~5 GB temporarily.${RESET}"
        echo "           Final corpus on disk is capped at ~800 MB."
    else
        echo "  Free disk    : ~${FREE_GB} GB on /tmp  (OK — final corpus capped at ~800 MB)"
    fi
fi
echo ""

# ---------------------------------------------------------------------------
# Step 01 — Download noisy corpus
# ---------------------------------------------------------------------------
banner "Step 01 — Download Noisy Corpus (tpn/pdfs → seed/docs/noisy_data/)"

if [ "$SKIP_NOISE" = true ]; then
    step_skip "Step 01"
else
    uv run python "$SCRIPT_DIR/01_download_noisy_data.py" $FORCE
    step_ok "Step 01"
fi

# ---------------------------------------------------------------------------
# Step 02 — Download true (K8s) corpus
# ---------------------------------------------------------------------------
banner "Step 02 — Download True Corpus (K8s docs → seed/docs/true_data/)"

if [ "$SKIP_TRUE" = true ]; then
    step_skip "Step 02"
else
    uv run python "$SCRIPT_DIR/02_download_true_data.py" $FORCE
    step_ok "Step 02"
fi

# ---------------------------------------------------------------------------
# Step 03 — Generate K8s ops SQL
# ---------------------------------------------------------------------------
banner "Step 03 — Generate K8s Ops SQL (seed/migrations/003_seed_k8s_ops.sql)"

SQL_ARGS="$FORCE"
if [ "$FAST_SQL" = true ]; then
    SQL_ARGS="$SQL_ARGS --fast"
fi
uv run python "$SCRIPT_DIR/03_generate_k8s_ops_db.py" $SQL_ARGS
step_ok "Step 03"

# ---------------------------------------------------------------------------
# Step 05 — Diversify true-corpus formats (TXT → PDF / DOCX / HTML / TXT mix)
# ---------------------------------------------------------------------------
banner "Step 05 — Diversify True-Corpus Formats (mixed PDF/DOCX/HTML/TXT)"

uv run python "$SCRIPT_DIR/05_diversify_true_formats.py" $FORCE
step_ok "Step 05"

# ---------------------------------------------------------------------------
# Step 04 — Validate
# ---------------------------------------------------------------------------
banner "Step 04 — Validate Dataset"

uv run python "$SCRIPT_DIR/04_validate_dataset.py" $STRICT
step_ok "Step 04"

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo -e "${GREEN}${BOLD}  ══════════════════════════════════════════${RESET}"
echo -e "${GREEN}${BOLD}  ALL STEPS COMPLETE — Dataset ready!${RESET}"
echo -e "${GREEN}${BOLD}  ══════════════════════════════════════════${RESET}"
echo ""
echo "  Next step: run 'make seed' to ingest documents into Qdrant"
echo "  and apply migrations to Postgres."
echo ""
