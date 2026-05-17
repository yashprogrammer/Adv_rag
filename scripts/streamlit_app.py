"""Streamlit UI for end-to-end testing of ADV RAG APIs.

Redesigned with use-case presets, clear RAG vs SQL UX, and rich feature toggles.
"""

from __future__ import annotations

import json
from typing import Any

import requests
import streamlit as st

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USE_CASES: dict[str, dict[str, Any]] = {
    "📝 Return Policy": {
        "question": "What is our return policy?",
        "mode": "rag",
        "search_mode": "hybrid",
        "enable_hyde": False,
        "enable_rerank": True,
        "enable_crag": True,
        "enable_self_reflective": False,
        "top_k": 5,
    },
    "📦 Order Status (SQL)": {
        "question": "How many orders were placed last month?",
        "mode": "sql",
        "search_mode": "dense",
        "enable_hyde": False,
        "enable_rerank": False,
        "enable_crag": False,
        "enable_self_reflective": False,
        "top_k": 3,
    },
    "💰 Revenue Query (SQL)": {
        "question": "What is the total revenue this quarter?",
        "mode": "sql",
        "search_mode": "dense",
        "enable_hyde": False,
        "enable_rerank": False,
        "enable_crag": False,
        "enable_self_reflective": False,
        "top_k": 3,
    },
    "🔍 Product Troubleshooting": {
        "question": "How do I reset my password?",
        "mode": "rag",
        "search_mode": "hybrid",
        "enable_hyde": True,
        "enable_rerank": True,
        "enable_crag": True,
        "enable_self_reflective": False,
        "top_k": 5,
    },
    "🏆 Deep Research (All Features)": {
        "question": "Explain our warranty and refund process in detail.",
        "mode": "rag",
        "search_mode": "hybrid",
        "enable_hyde": True,
        "enable_rerank": True,
        "enable_crag": True,
        "enable_self_reflective": True,
        "top_k": 10,
    },
    "🌐 Current Events (CRAG)": {
        "question": "What are the latest AI regulations in 2025?",
        "mode": "rag",
        "search_mode": "hybrid",
        "enable_hyde": False,
        "enable_rerank": True,
        "enable_crag": True,
        "enable_self_reflective": False,
        "top_k": 5,
    },
}

SEARCH_MODE_EMOJI = {"dense": "🧠", "sparse": "📝", "hybrid": "⚡"}

# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------


def _api_headers(token: str | None) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _safe_json(resp: requests.Response) -> Any:
    try:
        return resp.json()
    except Exception:
        return {"text": resp.text}


def _login(base_url: str, username: str, password: str) -> tuple[int, Any]:
    return _request(
        "POST",
        base_url,
        "/auth/login",
        json_body={"username": username, "password": password},
        retry_auth=False,
    )


def _refresh_token(base_url: str) -> bool:
    username = st.session_state.get("login_username")
    password = st.session_state.get("login_password")
    if not username or not password:
        return False
    status, payload = _login(base_url, username, password)
    if status == 200 and isinstance(payload, dict) and "token" in payload:
        st.session_state["token"] = payload["token"]
        return True
    return False


def _request(
    method: str,
    base_url: str,
    path: str,
    token: str | None = None,
    json_body: dict[str, Any] | None = None,
    files: dict[str, Any] | None = None,
    retry_auth: bool = True,
) -> tuple[int, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    headers = _api_headers(token)
    if files is not None:
        headers.pop("Content-Type", None)

    resp = requests.request(
        method=method,
        url=url,
        headers=headers,
        json=json_body,
        files=files,
        timeout=600,
    )
    payload = _safe_json(resp)

    if (
        retry_auth
        and resp.status_code == 401
        and isinstance(payload, dict)
        and payload.get("detail") == "Token has expired"
        and _refresh_token(base_url)
    ):
        headers = _api_headers(st.session_state.get("token"))
        if files is not None:
            headers.pop("Content-Type", None)
        resp = requests.request(
            method=method,
            url=url,
            headers=headers,
            json=json_body,
            files=files,
            timeout=600,
        )
        payload = _safe_json(resp)

    return resp.status_code, payload


# ---------------------------------------------------------------------------
# UI helpers
# ---------------------------------------------------------------------------


def _badge(label: str, color: str = "blue") -> str:
    """Return a small HTML badge."""
    colors = {
        "blue": "#dbeafe",
        "text_blue": "#1e40af",
        "green": "#d1fae5",
        "text_green": "#065f46",
        "yellow": "#fef9c3",
        "text_yellow": "#854d0e",
        "red": "#fee2e2",
        "text_red": "#991b1b",
        "purple": "#f3e8ff",
        "text_purple": "#6b21a8",
    }
    bg = colors.get(color, colors["blue"])
    fg = colors.get(f"text_{color}", colors["text_blue"])
    return f"""
    <span style="
        background-color: {bg};
        color: {fg};
        padding: 2px 10px;
        border-radius: 12px;
        font-size: 0.75rem;
        font-weight: 600;
        white-space: nowrap;
    ">{label}</span>
    """


def _render_answer_card(payload: dict[str, Any]) -> None:
    """Render the answer portion of a response (no status banner)."""
    answer = payload.get("answer", "")
    sources = payload.get("sources", [])
    confidence = payload.get("confidence", 0.0)
    cache_hit = payload.get("cache_hit", False)
    cost_saved = payload.get("cost_saved", "$0.00")
    meta = payload.get("metadata", {}) or {}

    with st.container(border=True):
        cols = st.columns([3, 1, 1, 1])
        with cols[0]:
            if cache_hit:
                st.markdown(_badge("⚡ Cache Hit", "green"), unsafe_allow_html=True)
            route = meta.get("route", "rag")
            st.markdown(_badge(f"Route: {route.upper()}", "purple"), unsafe_allow_html=True)
        with cols[1]:
            st.metric("Confidence", f"{confidence:.0%}")
        with cols[2]:
            st.metric("Sources", len(sources))
        with cols[3]:
            st.metric("Saved", cost_saved)

        st.divider()
        st.markdown("**Answer**")
        st.markdown(answer if answer else "_No answer returned._")

        if sources:
            with st.expander(f"📚 Sources ({len(sources)})", expanded=False):
                for i, src in enumerate(sources, 1):
                    st.markdown(f"{i}. {src}")

        chunks = meta.get("retrieved_chunks") or []
        if chunks:
            with st.expander(f"🧩 Retrieved Context Chunks ({len(chunks)})", expanded=True):
                st.caption(
                    "These are the chunks the LLM saw before generating the answer. "
                    "Flip a feature toggle and re-run to see how retrieval changes."
                )
                for i, ch in enumerate(chunks, 1):
                    src = ch.get("source", "?")
                    score = ch.get("score", 0.0)
                    text = ch.get("text", "")
                    with st.container(border=True):
                        cols = st.columns([3, 1])
                        with cols[0]:
                            st.markdown(f"**{i}. `{src}`**")
                        with cols[1]:
                            st.metric("score", f"{score:.3f}")
                        st.markdown(text)

        with st.expander("🔍 Metadata & Raw Response", expanded=False):
            st.json(payload)


def _render_pending_sql_card(pending_sql: dict[str, Any]) -> None:
    """Render a pending SQL approval card."""
    st.warning("⏳ SQL approval required — go to the **SQL Approval** tab to review.")
    with st.container(border=True):
        st.markdown("**🗄️ Generated SQL**")
        st.code(pending_sql.get("sql", ""), language="sql")
        st.caption(f"query_id: `{pending_sql.get('query_id', '')}`")
        if pending_sql.get("explanation"):
            st.info(pending_sql["explanation"])


def _render_response_card(status: int, payload: Any) -> None:
    """Render a nice response card instead of raw JSON dump."""
    if not isinstance(payload, dict):
        st.code(json.dumps(payload, indent=2), language="json")
        return

    # Top status banner
    if 200 <= status < 300:
        st.success("✅ Request succeeded")
    else:
        st.error(f"❌ Request failed — HTTP {status}")
        st.code(json.dumps(payload, indent=2), language="json")
        return

    # If there is a pending SQL block, show it prominently
    pending_sql = payload.get("pending_sql")
    if pending_sql:
        st.session_state["pending_sql"] = pending_sql
        _render_pending_sql_card(pending_sql)
        return

    _render_answer_card(payload)


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def _sidebar(base_url: str) -> str:
    with st.sidebar:
        st.image(
            "https://img.shields.io/badge/ADV--RAG-E--commerce%20Copilot-009688?style=for-the-badge&logo=fastapi",
            use_container_width=True,
        )
        st.markdown("---")
        base_url = st.text_input("API Base URL", value=base_url, key="base_url_input")
        st.markdown("[Swagger UI](http://localhost:8000/docs) · [ReDoc](http://localhost:8000/redoc)")
        st.markdown("---")

        # Quick health indicator
        if st.button("🩺 Ping Health", use_container_width=True):
            status, payload = _request("GET", base_url, "/admin/health")
            if status == 200 and isinstance(payload, dict):
                overall = payload.get("status", "unknown")
                if overall == "ok":
                    st.success("All systems operational ✅")
                else:
                    st.warning(f"Degraded — {overall}")
                st.json({k: v for k, v in payload.items() if k != "status"})
            else:
                st.error("Health check failed")

        st.markdown("---")
        st.caption("Session State")
        token = st.session_state.get("token", "")
        if token:
            st.success("Authenticated ✅")
            if st.button("🔓 Logout", use_container_width=True):
                st.session_state.clear()
                st.rerun()
        else:
            st.info("Not authenticated")

        return base_url


def _auth_section(base_url: str) -> None:
    st.header("🔐 Authentication")
    token = st.session_state.get("token")

    if token:
        st.success("You are logged in. Token stored in session.")
        return

    tab_reg, tab_log = st.tabs(["📝 Register", "🔑 Login"])

    with tab_reg:
        c1, c2 = st.columns(2)
        with c1:
            reg_user = st.text_input("Username", value="agent@demo.local", key="reg_user")
        with c2:
            reg_pass = st.text_input("Password", value="demo1234", type="password", key="reg_pass")
        if st.button("Create Account", use_container_width=True, key="btn_register"):
            status, payload = _request(
                "POST", base_url, "/auth/register",
                json_body={"username": reg_user, "password": reg_pass},
            )
            if status in (200, 201) and isinstance(payload, dict) and "token" in payload:
                st.session_state["token"] = payload["token"]
                st.session_state["login_username"] = reg_user
                st.session_state["login_password"] = reg_pass
                st.success("Registered & logged in! 🎉")
                st.rerun()
            else:
                _render_response_card(status, payload)

    with tab_log:
        c1, c2 = st.columns(2)
        with c1:
            log_user = st.text_input("Username", value="agent@demo.local", key="log_user")
        with c2:
            log_pass = st.text_input("Password", value="demo1234", type="password", key="log_pass")
        if st.button("Login", use_container_width=True, key="btn_login"):
            status, payload = _login(base_url, log_user, log_pass)
            if status == 200 and isinstance(payload, dict) and "token" in payload:
                st.session_state["token"] = payload["token"]
                st.session_state["login_username"] = log_user
                st.session_state["login_password"] = log_pass
                st.success("Logged in! 🎉")
                st.rerun()
            else:
                _render_response_card(status, payload)


def _upload_section(base_url: str) -> None:
    st.header("📤 Upload Document")
    token = st.session_state.get("token")
    if not token:
        st.info("Login first to upload documents.")
        return

    uploaded = st.file_uploader("Choose a PDF", type=["pdf"], key="pdf_uploader")

    if uploaded is None:
        st.caption("Select a PDF above to see upload options.")
        return

    # File info card
    size_kb = len(uploaded.getvalue()) / 1024
    with st.container(border=True):
        c1, c2, c3 = st.columns([2, 1, 1])
        with c1:
            st.markdown(f"**📄 {uploaded.name}**")
        with c2:
            st.markdown(f"`{size_kb:.1f} KB`")
        with c3:
            st.markdown("`PDF ✅`")

    # First-run warning
    st.info(
        "⏱️ **First upload may take 1–3 minutes** — Docling downloads OCR/layout models (~400 MB) on first use. "
        "Subsequent uploads are typically under 10 seconds.",
        icon="⏳",
    )

    if st.button("🚀 Upload & Index", use_container_width=True, key="btn_upload"):
        files = {"file": (uploaded.name, uploaded.getvalue(), "application/pdf")}

        with st.status("Indexing document…", expanded=True) as status:
            st.write("📡 **Step 1/3** — Sending file to API…")

            try:
                resp = requests.request(
                    method="POST",
                    url=f"{base_url.rstrip('/')}/documents/upload",
                    headers={"Authorization": f"Bearer {token}"},
                    files=files,
                    timeout=600,
                )
                status_code = resp.status_code
                payload = _safe_json(resp)
            except requests.exceptions.Timeout:
                status.update(label="⏱️ Upload timed out", state="error", expanded=True)
                st.error(
                    "The upload timed out after 10 minutes. This usually means Docling is still downloading models.\n\n"
                    "**What to do:**\n"
                    "1. Check the API server logs — you should see Docling download progress\n"
                    "2. Wait for the download to finish (one-time only)\n"
                    "3. Try uploading again — it will be fast after models are cached"
                )
                return
            except requests.exceptions.ConnectionError:
                status.update(label="❌ Connection failed", state="error", expanded=True)
                st.error("Could not connect to the API. Is the server running at the configured base URL?")
                return

            if status_code in (200, 201) and isinstance(payload, dict):
                chunks = payload.get("chunks_indexed", 0)
                page_count = payload.get("page_count")
                doc_id = payload.get("doc_id", uploaded.name)

                st.write(f"✅ **Step 2/3** — Parsed {chunks} chunk(s)" + (f" from {page_count} page(s)" if page_count else ""))
                st.write("✅ **Step 3/3** — Embeddings created & vectors upserted to Qdrant")
                status.update(label=f"🎉 Indexed {chunks} chunks successfully", state="complete")

                with st.container(border=True):
                    st.markdown(f"**🎉 Document Indexed**")
                    cols = st.columns([3, 1, 1])
                    with cols[0]:
                        st.markdown(f"`{doc_id}`")
                    with cols[1]:
                        st.metric("Chunks", chunks)
                    with cols[2]:
                        st.metric("Pages", page_count or "—")
                    st.caption("The document is now searchable via the Query tab.")
            else:
                status.update(label=f"❌ Upload failed (HTTP {status_code})", state="error", expanded=True)
                _render_response_card(status_code, payload)


def _query_section(base_url: str) -> None:
    st.header("💬 Ask a Question")
    token = st.session_state.get("token")
    if not token:
        st.info("Login first to use query endpoints.")
        return

    # --- Persisted results from previous runs --------------------------------
    last_result = st.session_state.get("last_query_result")
    if last_result and isinstance(last_result, dict):
        with st.container(border=True):
            st.markdown("**📌 Last Query Result**")
            st.caption(f"Question: `{last_result.get('question', '—')}`")
            _render_answer_card(last_result["payload"])
        if st.button("🗑️ Dismiss result", key="dismiss_query_result"):
            st.session_state.pop("last_query_result", None)
            st.rerun()
        st.divider()

    pending = st.session_state.get("pending_sql")
    if pending and isinstance(pending, dict):
        st.info(
            f"⏳ You have a pending SQL approval (query_id: `{pending.get('query_id', '')}`). "
            "Go to the **SQL Approval** tab to approve or reject it.",
            icon="🗄️",
        )

    # Use-case presets
    st.markdown("**🎯 Use Case Presets** — pick one to auto-fill settings:")
    preset_cols = st.columns(len(USE_CASES))
    for idx, (label, cfg) in enumerate(USE_CASES.items()):
        with preset_cols[idx]:
            if st.button(label, use_container_width=True, key=f"preset_{idx}"):
                for k, v in cfg.items():
                    st.session_state[f"q_{k}"] = v
                st.rerun()

    st.divider()

    # Query input
    question = st.text_area(
        "Your question",
        value=st.session_state.get("q_question", "What is our return policy?"),
        height=80,
        key="q_question",
        placeholder="e.g. How many orders last month? | What is the warranty policy?",
    )

    # Feature toggles
    with st.expander("⚙️ RAG Feature Toggles", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            search_mode = st.selectbox(
                "Search mode",
                ["dense", "sparse", "hybrid"],
                index=["dense", "sparse", "hybrid"].index(st.session_state.get("q_search_mode", "hybrid")),
                format_func=lambda x: f"{SEARCH_MODE_EMOJI[x]} {x.capitalize()}",
                key="q_search_mode",
            )
        with c2:
            top_k = st.slider(
                "top_k",
                min_value=1, max_value=50,
                value=st.session_state.get("q_top_k", 5),
                key="q_top_k",
            )
        with c3:
            enable_hyde = st.toggle(
                "HyDE",
                value=st.session_state.get("q_enable_hyde", False),
                key="q_enable_hyde",
                help="Generate hypothetical answer embeddings to improve retrieval",
            )
        with c4:
            enable_rerank = st.toggle(
                "Rerank",
                value=st.session_state.get("q_enable_rerank", True),
                key="q_enable_rerank",
                help="Cross-encoder reranking of retrieved chunks",
            )

        c5, c6, _ = st.columns(3)
        with c5:
            enable_crag = st.toggle(
                "CRAG",
                value=st.session_state.get("q_enable_crag", True),
                key="q_enable_crag",
                help="CRAG relevance grading + Tavily web-search fallback",
            )
        with c6:
            enable_self_reflective = st.toggle(
                "Self-Reflective",
                value=st.session_state.get("q_enable_self_reflective", False),
                key="q_enable_self_reflective",
                help="Self-RAG reflection loop (max 2 retries)",
            )

        # Visual summary of active features
        active = []
        if enable_hyde:
            active.append("HyDE")
        if enable_rerank:
            active.append("Rerank")
        if enable_crag:
            active.append("CRAG")
        if enable_self_reflective:
            active.append("Self-Reflective")
        active_str = " · ".join(active) if active else "None (basic retrieval)"
        st.caption(f"Active features: **{active_str}** | Search: **{search_mode}** | top_k: **{top_k}**")

    # Submit
    if st.button("🚀 Submit Query", use_container_width=True, key="btn_query"):
        body = {
            "question": question,
            "search_mode": search_mode,
            "enable_hyde": enable_hyde,
            "enable_rerank": enable_rerank,
            "enable_crag": enable_crag,
            "enable_self_reflective": enable_self_reflective,
            "top_k": top_k,
        }
        with st.spinner("Running query pipeline…"):
            status, payload = _request(
                "POST", base_url, "/query",
                token=token, json_body=body,
            )
        _render_response_card(status, payload)

        # Persist completed results (not pending SQL) so they survive tab switches
        if status == 200 and isinstance(payload, dict) and not payload.get("pending_sql"):
            st.session_state["last_query_result"] = {
                "question": question,
                "payload": payload,
            }

        # Track in session history
        if status == 200 and isinstance(payload, dict):
            history = st.session_state.get("query_history", [])
            history.append({
                "question": question,
                "route": (payload.get("metadata") or {}).get("route", "rag"),
                "confidence": payload.get("confidence", 0.0),
                "cache_hit": payload.get("cache_hit", False),
            })
            st.session_state["query_history"] = history[-20:]


def _sql_approval_section(base_url: str) -> None:
    st.header("🗄️ SQL Approval")
    token = st.session_state.get("token")
    pending = st.session_state.get("pending_sql")

    if not token:
        st.info("Login first.")
        return

    # --- Show previously approved / rejected result --------------------------
    last_sql = st.session_state.get("last_sql_result")
    if last_sql and isinstance(last_sql, dict):
        action = last_sql.get("action", "approved")
        label = "✅ Approved Result" if action == "approved" else "❌ Rejected Result"
        with st.container(border=True):
            st.markdown(f"**{label}**")
            st.caption(f"query_id: `{last_sql.get('query_id', '—')}`")
            if action == "approved":
                _render_answer_card(last_sql["payload"])
            else:
                st.markdown("_SQL query was rejected._")
        if st.button("🗑️ Dismiss result", key="dismiss_sql_result"):
            st.session_state.pop("last_sql_result", None)
            st.rerun()
        st.divider()

    if not pending:
        st.info("No pending SQL block. Ask a data question (e.g. *How many orders last month?*) to trigger Text2SQL.")
        return

    with st.container(border=True):
        st.markdown("### ⏳ Pending SQL Review")
        st.code(pending.get("sql", ""), language="sql")
        st.caption(f"query_id: `{pending.get('query_id', '')}`")
        if pending.get("explanation"):
            st.info(pending["explanation"])

        c_approve, c_reject = st.columns(2)
        with c_approve:
            if st.button("✅ Approve & Execute", use_container_width=True, type="primary"):
                with st.spinner("Executing SQL…"):
                    status, payload = _request(
                        "POST", base_url, "/query/sql/execute",
                        token=token,
                        json_body={"query_id": pending.get("query_id"), "approved": True},
                    )
                _render_response_card(status, payload)
                if 200 <= status < 300 and isinstance(payload, dict):
                    st.session_state["last_sql_result"] = {
                        "query_id": pending.get("query_id"),
                        "action": "approved",
                        "payload": payload,
                    }
                    st.session_state.pop("pending_sql", None)
                    st.rerun()
        with c_reject:
            if st.button("❌ Reject", use_container_width=True):
                with st.spinner("Rejecting…"):
                    status, payload = _request(
                        "POST", base_url, "/query/sql/execute",
                        token=token,
                        json_body={"query_id": pending.get("query_id"), "approved": False},
                    )
                _render_response_card(status, payload)
                if 200 <= status < 300:
                    st.session_state["last_sql_result"] = {
                        "query_id": pending.get("query_id"),
                        "action": "rejected",
                        "payload": {},
                    }
                    st.session_state.pop("pending_sql", None)
                    st.rerun()


def _history_section() -> None:
    st.header("📜 Recent Queries")
    history = st.session_state.get("query_history", [])
    if not history:
        st.caption("No queries yet this session.")
        return
    for item in reversed(history[-10:]):
        with st.container(border=True):
            st.markdown(f"**{item['question']}**")
            cols = st.columns([1, 1, 1, 3])
            cols[0].caption(f"Route: {item.get('route', '—')}")
            cols[1].caption(f"Conf: {item.get('confidence', 0):.0%}")
            cols[2].caption(f"Cache: {'✅' if item.get('cache_hit') else '❌'}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    st.set_page_config(
        page_title="ADV RAG — E-commerce Copilot",
        page_icon="🔮",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    default_url = "http://localhost:8000"
    base_url = _sidebar(default_url)

    # Title area
    c_title, c_status = st.columns([3, 1])
    with c_title:
        st.title("🔮 ADV RAG")
        st.caption("E-commerce Customer Support Copilot — Text2SQL + Core RAG + Security + Caching")
    with c_status:
        token = st.session_state.get("token")
        if token:
            st.markdown(_badge("Authenticated", "green"), unsafe_allow_html=True)
        else:
            st.markdown(_badge("Guest", "yellow"), unsafe_allow_html=True)

    st.divider()

    # Main tabs
    tab_auth, tab_query, tab_upload, tab_sql, tab_history = st.tabs([
        "🔐 Auth",
        "💬 Query",
        "📤 Upload",
        "🗄️ SQL Approval",
        "📜 History",
    ])

    with tab_auth:
        _auth_section(base_url)
    with tab_query:
        _query_section(base_url)
    with tab_upload:
        _upload_section(base_url)
    with tab_sql:
        _sql_approval_section(base_url)
    with tab_history:
        _history_section()


if __name__ == "__main__":
    main()
