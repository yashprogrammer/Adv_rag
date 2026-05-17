# Eval Pipeline — Quickstart

Ragas-based evaluation harness for the Advanced RAG e-commerce copilot.

## Prerequisites

1. Local stack running:
   ```bash
   docker compose up -d
   ```

2. Seed DB ingested:
```bash
make seed
# or: uv run python scripts/seed_db.py
```

3. Seed PDFs generated and uploaded:
```bash
uv run python seed/docs/generate_pdfs.py
for f in seed/docs/*.pdf; do curl -F "file=@$f" http://localhost:8000/documents/upload; done
```

4. OpenAI API key set:
   ```bash
   export OPENAI_API_KEY=sk-...
   ```

## Run evaluation

### Baseline (naive RAG)
```bash
make eval-baseline
```

### All features enabled
```bash
make eval-all
```

### Diff baseline vs all-features
```bash
make eval-diff
```

### Individual profiles
```bash
make eval-hybrid
make eval-rerank
make eval-hyde
make eval-crag
```

## Filter by feature

Run only goldens that demonstrate a specific feature (plus baseline controls):

```bash
uv run python -m eval.run_ragas --profile hybrid+rerank+hyde --filter hyde
uv run python -m eval.run_ragas --profile hybrid+rerank+crag --filter crag
```

## Inspect results

Results are written to `eval/results/<timestamp>_<profile>.json`.

## What gets skipped

In **service mode** (default):
- SQL-only goldens (`q-017`, `q-018`) — skipped, require API mode
- Hybrid RAG+SQL goldens (`q-019`, `q-020`) — skipped, require API mode
- CRAG web_fallback goldens (`q-013`, `q-014`) — skipped if `TAVILY_API_KEY` is unset

## Profiles

| Profile | Flags |
|---------|-------|
| `naive` | dense, no HyDE, no rerank, no CRAG, no reflection |
| `sparse_only` | sparse (falls back to hybrid in current impl) |
| `hybrid` | hybrid, no rerank |
| `hybrid+rerank` | hybrid + rerank |
| `hybrid+rerank+hyde` | hybrid + rerank + HyDE |
| `hybrid+rerank+crag` | hybrid + rerank + CRAG |
| `all` | hybrid + rerank + HyDE + CRAG + self-reflection |

## Troubleshooting

**Ragas column errors:** We pin `ragas>=0.2.0` in `pyproject.toml`. If you see metric errors, verify the installed version matches the column names in `eval/ragas_adapter.py`.

**No chunks returned:** Ensure seed PDFs are uploaded and Qdrant is populated. Run a single question manually:
```bash
uv run python -c "
from app.services.rag_service import run_rag_with_trace
resp, chunks = run_rag_with_trace('What is your return policy?', {})
print(len(chunks), resp.answer)
"
```
