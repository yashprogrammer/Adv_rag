# Feature Test Guide

Complete test commands and verification steps for every major feature.

> **Prerequisites**
> - App running: `uvicorn app.main:app --reload`
> - Infra up: `docker compose up -d`
> - You have a valid JWT token (`<token>`) from `/auth/login`
> - Admin JWT (`<admin_token>`) for cache stats

---

## 1. RAG and its Types

Base URL: `POST http://localhost:8000/query`

### 1.1 Dense Retrieval Only
```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is our return policy?",
    "search_mode": "dense",
    "enable_hyde": false,
    "enable_rerank": false,
    "enable_crag": false,
    "enable_self_reflective": false,
    "top_k": 5
  }'
```
**Verify:** Response contains `sources` with vector-search chunks. No web-search fallback.

### 1.2 Sparse Retrieval Only
```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is our return policy?",
    "search_mode": "sparse",
    "enable_hyde": false,
    "enable_rerank": false,
    "enable_crag": false,
    "enable_self_reflective": false,
    "top_k": 5
  }'
```
**Verify:** Answer derived from sparse (BM25-style) inverted-index matches.

### 1.3 Hybrid Search (Dense + Sparse + RRF)
```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What payment methods do you accept?",
    "search_mode": "hybrid",
    "enable_hyde": false,
    "enable_rerank": false,
    "enable_crag": false,
    "enable_self_reflective": false,
    "top_k": 5
  }'
```
**Verify:** Sources include chunks scored by Reciprocal Rank Fusion (RRF). Check logs for `rrf_k` usage.

### 1.4 HyDE (Hypothetical Document Embeddings)
```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How do I track my order?",
    "search_mode": "hybrid",
    "enable_hyde": true,
    "enable_rerank": false,
    "enable_crag": false,
    "enable_self_reflective": false,
    "top_k": 5
  }'
```
**Verify:** Logs show HyDE retriever generating ~3 hypothetical answers before embedding search. Look for `hyde` in the retrieval path.

### 1.5 Reranking (Cross-Encoder / Voyage)
```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What payment methods do you accept?",
    "search_mode": "hybrid",
    "enable_hyde": false,
    "enable_rerank": true,
    "enable_crag": false,
    "enable_self_reflective": false,
    "top_k": 5
  }'
```
**Verify:** Logs mention `reranker` or `cross-encoder` / `voyage`. `sources` order differs from raw retrieval order.

### 1.6 CRAG + Tavily Web-Search Fallback
Ask something **not** in your uploaded docs to force low relevance:
```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is the latest iPhone 16 price on Amazon?",
    "search_mode": "hybrid",
    "enable_hyde": false,
    "enable_rerank": true,
    "enable_crag": true,
    "enable_self_reflective": false,
    "top_k": 5
  }'
```
**Verify:**
- Logs show `crag` grading step with low relevance score (< `CRAG_RELEVANCE_THRESHOLD`).
- Tavily web search is invoked (`tavily` in logs).
- Final answer cites web sources.

### 1.7 Self-Reflective RAG
```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "Tell me about our warranty coverage",
    "search_mode": "hybrid",
    "enable_hyde": false,
    "enable_rerank": true,
    "enable_crag": true,
    "enable_self_reflective": true,
    "top_k": 5
  }'
```
**Verify:** Logs show a reflection loop — if the grader gives a low score, the pipeline regenerates (max 2 retries). Look for `reflect` or `regenerate` in LangGraph state transitions.

### 1.8 Full RAG Pipeline (All Features On)
```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How do returns work for international orders?",
    "search_mode": "hybrid",
    "enable_hyde": true,
    "enable_rerank": true,
    "enable_crag": true,
    "enable_self_reflective": true,
    "top_k": 5
  }'
```
**Verify:** Trace through logs: `intent` → `hybrid` → `hyde` → `rerank` → `crag` → (`tavily` if needed) → `spotlighting` → `generate` → `reflect` → `validate`.

---

## 2. SQL Execution

### 2.1 SQL Generation + Human-in-the-Loop Approval
```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "How many orders were placed last month?"
  }'
```
**Expected Response:**
```json
{
  "type": "pending_sql",
  "query_id": "<query_id>",
  "sql": "SELECT COUNT(*) FROM orders WHERE created_at >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month') ...",
  "explanation": "Counts orders placed in the previous calendar month."
}
```

### 2.2 Approve and Execute SQL
```bash
curl -X POST http://localhost:8000/query/sql/execute \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "query_id": "<query_id>",
    "approved": true
  }'
```
**Verify:** Response contains `sql_result` rows and a natural-language `answer`.

### 2.3 Reject SQL
```bash
curl -X POST http://localhost:8000/query/sql/execute \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "query_id": "<query_id>",
    "approved": false
  }'
```
**Verify:** Response indicates SQL was skipped. No database mutation occurs.

### 2.4 SELECT-Only Enforcement
Inspect any generated SQL from step 2.1:
```bash
echo '<sql_from_response>' | grep -iE '\b(INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|TRUNCATE|GRANT)\b'
```
**Verify:** No matches. The SQL service enforces a keyword blocklist and should only produce `SELECT` statements.

### 2.5 Schema Introspection
Ask about a column you know exists:
```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What are the top 5 products by total revenue?"
  }'
```
**Verify:** Generated SQL correctly joins `orders` → `order_items` → `products` using actual table/column names loaded from Postgres introspection.

---

## 3. Caching and its Types

Use the admin endpoint to inspect cache telemetry:
```bash
curl -X GET http://localhost:8000/admin/cache/stats \
  -H "Authorization: Bearer <admin_token>"
```

### 3.1 Intent Router Cache (TTL: 24h)
```bash
# First call — cold cache
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is our return policy?", "search_mode": "hybrid"}'

# Second call — should hit intent cache
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is our return policy?", "search_mode": "hybrid"}'
```
**Verify:** `GET /admin/cache/stats` shows `intent_router` hits incremented. Look for `hit` vs `miss` counters.

### 3.2 Embedding Cache (TTL: 7d)
Upload or query a document with a unique sentence, then query again:
```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "Explain the supercalifragilisticexpialidocious clause.", "search_mode": "hybrid"}'
```
Run the exact same query a second time.
**Verify:** `embedding` tier in `/admin/cache/stats` shows a hit. No second OpenAI embedding API call is made (check logs or latency drop).

### 3.3 SQL Generation Cache (TTL: 24h)
```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "How many orders were placed last month?"}'
# Approve or reject, then ask again with the same question
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"question": "How many orders were placed last month?"}'
```
**Verify:** `sql_gen` cache hits increase. The second request should return the **same SQL** instantly without LLM generation.

### 3.4 SQL Result Cache (TTL: 15m)
Approve a SQL query, then approve the **same** SQL query again within 15 minutes:
```bash
# Run 2.1 → get query_id_1 → approve → run 2.1 again → get query_id_2 → approve
```
**Verify:** `sql_result` cache hits increase. The second approval returns results without hitting Postgres.

### 3.5 RAG Answer Cache (TTL: 1h)
```bash
curl -X POST http://localhost:8000/query \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "What is our return policy?",
    "search_mode": "hybrid",
    "enable_hyde": false,
    "enable_rerank": false,
    "enable_crag": false
  }'
```
Run the identical request again.
**Verify:** `rag_answer` cache hits increase. Response time should drop significantly on the second call.

### 3.6 Doc Deduplication Cache (Indefinite)
Upload the same PDF twice:
```bash
curl -X POST http://localhost:8000/documents/upload \
  -H "Authorization: Bearer <admin_token>" \
  -F "file=@seed/demo_policy.pdf"

curl -X POST http://localhost:8000/documents/upload \
  -H "Authorization: Bearer <admin_token>" \
  -F "file=@seed/demo_policy.pdf"
```
**Verify:** Second upload is skipped or returns `already_exists`. Logs show SHA-256 deduplication hit. No duplicate chunks are embedded or upserted to Qdrant.

---

## Quick Verification Checklist

| Feature | Test | Pass Criteria |
|---------|------|---------------|
| Dense RAG | `search_mode: dense` | Answer from vector store, no web fallback |
| Sparse RAG | `search_mode: sparse` | Answer from sparse index |
| Hybrid RAG | `search_mode: hybrid` | RRF fusion in logs |
| HyDE | `enable_hyde: true` | Hypothetical docs generated in logs |
| Rerank | `enable_rerank: true` | Reranker module in logs, reordered sources |
| CRAG | `enable_crag: true` + off-topic query | Tavily fallback triggered on low relevance |
| Self-Reflect | `enable_self_reflective: true` | Reflection/regeneration loop in logs |
| SQL Gen | Data question | `pending_sql` block returned |
| SQL Approve | `approved: true` | SQL executes, rows + answer returned |
| SQL Reject | `approved: false` | SQL skipped safely |
| SELECT-only | Inspect generated SQL | No DML/DDL keywords |
| Intent Cache | Same question twice | `intent_router` hit counter + |
| Embedding Cache | Same question twice | `embedding` hit counter + |
| SQL Gen Cache | Same SQL question twice | `sql_gen` hit counter + |
| SQL Result Cache | Same SQL approved twice | `sql_result` hit counter + |
| RAG Answer Cache | Same RAG question twice | `rag_answer` hit counter + |
| Doc Dedup | Same PDF uploaded twice | Second upload deduplicated |

---

## Tips

1. **Watch the logs** — `tail -f` your uvicorn output to see LangGraph node transitions (`route_intent`, `retrieve_rag`, `generate_sql_node`, etc.).
2. **Reset caches** — Restart Redis or flush the Upstash database to get cold-cache behavior.
3. **Use the Streamlit tester** — `streamlit run scripts/streamlit_app.py` provides a visual UI for all of the above without writing curl commands.
