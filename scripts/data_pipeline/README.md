# ADV RAG — Data Pipeline

## Philosophy: 95% Noise / 5% Signal

The entire advanced RAG research literature is built on a simple insight: **retrieval techniques only show measurable improvement when there is enough noise to separate them from naive baselines.**

This pipeline assembles a corpus with a deliberate **95% noise / 5% signal** split:

| Corpus slice | Count | Source | Purpose |
|---|---|---|---|
| `true_data` | 50 files | Kubernetes official docs | The *signal* — what the RAG system must find |
| `noisy_data` | 950 files | `github.com/tpn/pdfs` (random PDFs/DOCX/TXT/HTML) | The *noise* — irrelevant distractors |
| `k8s_ops_db` | 1 SQL file | Synthetic Faker data | Text2SQL demonstration data |

With 95% noise, a naive cosine-similarity retrieval will regularly return irrelevant docs. Every advanced technique — HyDE, cross-encoder re-ranking, CRAG, Self-RAG — demonstrates a **statistically significant, visually obvious** improvement in the Ragas eval dashboard.

---

## Data Flow

```mermaid
flowchart TD
    A[github.com/tpn/pdfs] -->|git clone --depth 1| B[/tmp/adv_rag_pipeline_clones/tpn_pdfs]
    B -->|random sample\n950 files, seed=42| C[seed/docs/noisy_data/]

    D[github.com/FareedKhan-dev/\nscalable-rag-pipeline] -->|git clone --depth 1\n Strategy A| E[/tmp/.../fareed_rag_pipeline/true_data/]
    E -->|copy 50 files| F[seed/docs/true_data/]

    G[kubernetes.io/docs/] -->|HTTP scrape\nStrategy B fallback| F

    H[faker + random.Random\nseed=42] -->|generate 187K rows| I[seed/migrations/003_seed_k8s_ops.sql]

    C & F & I -->|04_validate| J{Validation\nReport}
    J -->|PASS| K[make seed\nIngest into Qdrant + Postgres]
    J -->|FAIL| L[Fix + re-run pipeline]
```

---

## How to Run

### Prerequisites

| Requirement | Check |
|---|---|
| `uv` installed | `uv --version` |
| ~5 GB free on `/tmp` | Temporary repo clone (deleted after sampling) |
| Network access to `github.com` and `kubernetes.io` | Required for steps 01–02 |
| `uv sync --extra dev` run once | Installs `faker`, `pyyaml`, etc. |

> **Final corpus on disk is capped at ~800 MB** (see `noise_max_total_mb` in
> `config.yaml`). The `/tmp` requirement is only for the transient clone of
> the noise repo, which is removed once sampling completes.

### Full run (recommended)

```bash
# From the project root:
bash scripts/data_pipeline/run_all.sh
```

### Individual steps

```bash
# Step 1 — Download 950 noisy files (~30–60 min, network-bound)
uv run python scripts/data_pipeline/01_download_noisy_data.py

# Step 2 — Download 50 K8s true docs (~2–5 min)
uv run python scripts/data_pipeline/02_download_true_data.py

# Step 3 — Generate 187K-row K8s ops SQL (~5 min, CPU-bound)
uv run python scripts/data_pipeline/03_generate_k8s_ops_db.py

# Step 4 — Validate everything
uv run python scripts/data_pipeline/04_validate_dataset.py
```

### Makefile shortcut

```bash
make seed-data
```

### Flags

| Flag | Script(s) | Effect |
|---|---|---|
| `--force` | 01, 02, 03 | Re-download/regenerate even if output exists |
| `--skip-noise` | `run_all.sh` | Skip step 01 (noise already downloaded) |
| `--skip-true` | `run_all.sh` | Skip step 02 |
| `--fast-sql` | `run_all.sh`, 03 | Generate 1/10 row counts for smoke-testing |
| `--strict` | `run_all.sh`, 04 | Treat validation warnings as failures |
| `--strategy a/b/auto` | 02 | Force Strategy A (clone) or B (scrape) |

---

## Expected Output Sizes

```
seed/docs/true_data/    ~50 files     ~25–40 MB   (K8s docs)
seed/docs/noisy_data/   ~300–950 files ~600–800 MB (random PDFs etc., size-capped)
seed/migrations/003…    1 file        ~18–22 MB   (synthetic SQL)
─────────────────────────────────────────────────────────────
TOTAL                   ~350–1,000 files  ~650–860 MB
```

> The noisy corpus stops sampling as soon as its size budget
> (`noise_max_total_mb`, default 800 MB) is exhausted — so you'll often see
> 300–800 files rather than the full 950, depending on the average file size
> in the random sample.

> Actual sizes depend on which files are sampled from `tpn/pdfs` and which
> K8s pages are available.  The `random_seed: 42` in `config.yaml` ensures
> the same 950 files are selected across all re-runs.

---

## Configuration

All tuneable parameters live in `scripts/data_pipeline/config.yaml`.  No
Python changes needed for common adjustments:

```yaml
corpus:
  noise_count: 950   # ← change this to 200 for a faster first iteration
  true_count:  50
  random_seed: 42    # ← change to get a different sample

sql_generator:
  row_counts:
    pods: 50000      # ← reduce to 5000 for a fast smoke-test
```

---

## Troubleshooting

### `git clone` hangs / times out on Step 01

The `tpn/pdfs` repo is ~6–8 GB. On slow connections it can take 1–2 hours.

**Options:**
1. Run overnight via `nohup bash scripts/data_pipeline/run_all.sh > pipeline.log 2>&1 &`
2. Reduce `noise_count` to 100 in `config.yaml`, which still shows meaningful degradation
3. Use `--keep-clone` flag to avoid re-cloning on subsequent runs

### Step 02 falls back to Strategy B (kubernetes.io scrape)

This is expected behaviour when the FareedKhan repo is unavailable or empty. The scraper uses polite 0.5s delays and produces `.txt` files with the full page text. Quality is similar to the primary strategy.

### `uv run` fails with `ModuleNotFoundError: No module named 'yaml'`

`pyyaml` is a transitive dependency of `langgraph` and should already be present. If not:

```bash
uv add pyyaml
# or just:
uv sync --extra dev
```

### SQL file is much smaller than ~20 MB

This typically means the `--fast` flag was used (intentional 1/10 scale). Run without `--fast-sql` for the full dataset.

### Not enough disk space on `/tmp`

Configure a different temp clone directory in `config.yaml`:

```yaml
output:
  temp_clone_dir: "/your/large/disk/adv_rag_tmp"
```

---

## Files in this directory

| File | Purpose |
|---|---|
| `config.yaml` | All tuneable parameters |
| `01_download_noisy_data.py` | Clone tpn/pdfs, sample 950 files |
| `02_download_true_data.py` | Clone/scrape K8s docs (50 files) |
| `03_generate_k8s_ops_db.py` | Synthetic SQL with Faker (187K rows) |
| `04_validate_dataset.py` | Final validation + summary report |
| `run_all.sh` | Bash orchestrator for all 4 steps |
| `README.md` | This file |
