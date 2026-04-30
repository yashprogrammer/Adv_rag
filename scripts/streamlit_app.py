"""Streamlit UI for end-to-end testing of ADV RAG APIs."""

from __future__ import annotations

import json
from typing import Any

import requests
import streamlit as st


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


def _show_response(status: int, payload: Any) -> None:
    if 200 <= status < 300:
        st.success(f"Status: {status}")
    else:
        st.error(f"Status: {status}")
    st.code(json.dumps(payload, indent=2), language="json")


def _auth_section(base_url: str) -> None:
    st.subheader("1) Auth")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("Register")
        reg_user = st.text_input("Register username", value="tester@demo.local", key="reg_user")
        reg_pass = st.text_input("Register password", value="test1234", type="password", key="reg_pass")
        if st.button("Register", key="btn_register"):
            status, payload = _request(
                "POST",
                base_url,
                "/auth/register",
                json_body={"username": reg_user, "password": reg_pass},
            )
            _show_response(status, payload)
            if status in (200, 201) and isinstance(payload, dict) and "token" in payload:
                st.session_state["token"] = payload["token"]
                st.session_state["login_username"] = reg_user
                st.session_state["login_password"] = reg_pass

    with col2:
        st.markdown("Login")
        log_user = st.text_input("Login username", value="tester@demo.local", key="log_user")
        log_pass = st.text_input("Login password", value="test1234", type="password", key="log_pass")
        if st.button("Login", key="btn_login"):
            status, payload = _login(base_url, log_user, log_pass)
            _show_response(status, payload)
            if status == 200 and isinstance(payload, dict) and "token" in payload:
                st.session_state["token"] = payload["token"]
                st.session_state["login_username"] = log_user
                st.session_state["login_password"] = log_pass

    token = st.session_state.get("token", "")
    token_area = st.text_area("Current bearer token", value=token, height=90, key="token_area")
    if token_area and token_area != token:
        st.session_state["token"] = token_area.strip()


def _health_section(base_url: str) -> None:
    st.subheader("2) Health")
    if st.button("Check /admin/health"):
        status, payload = _request("GET", base_url, "/admin/health")
        _show_response(status, payload)


def _upload_section(base_url: str) -> None:
    st.subheader("3) Upload PDF")
    token = st.session_state.get("token")
    if not token:
        st.info("Login first to upload documents.")
        return

    uploaded = st.file_uploader("Choose PDF", type=["pdf"], key="pdf_uploader")
    if st.button("Upload Document"):
        if uploaded is None:
            st.warning("Select a PDF file first.")
            return
        files = {"file": (uploaded.name, uploaded.getvalue(), "application/pdf")}
        with st.spinner("Uploading and processing PDF... this can take a while on first run"):
            status, payload = _request(
                "POST",
                base_url,
                "/documents/upload",
                token=token,
                files=files,
            )
            _show_response(status, payload)


def _query_section(base_url: str) -> None:
    st.subheader("4) Query (RAG / SQL / Hybrid)")
    token = st.session_state.get("token")
    if not token:
        st.info("Login first to use query endpoints.")
        return

    question = st.text_area(
        "Question",
        value="What is the return policy?",
        height=100,
        key="question_input",
    )

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        search_mode = st.selectbox("search_mode", ["dense", "sparse", "hybrid"], index=2)
    with c2:
        enable_hyde = st.checkbox("enable_hyde", value=False)
    with c3:
        enable_rerank = st.checkbox("enable_rerank", value=True)
    with c4:
        enable_crag = st.checkbox("enable_crag", value=True)

    enable_self_reflective = st.checkbox("enable_self_reflective", value=False)
    top_k = st.slider("top_k", min_value=1, max_value=20, value=5)

    if st.button("Submit /query"):
        body = {
            "question": question,
            "search_mode": search_mode,
            "enable_hyde": enable_hyde,
            "enable_rerank": enable_rerank,
            "enable_crag": enable_crag,
            "enable_self_reflective": enable_self_reflective,
            "top_k": top_k,
        }
        status, payload = _request("POST", base_url, "/query", token=token, json_body=body)
        _show_response(status, payload)

        if isinstance(payload, dict) and payload.get("pending_sql"):
            st.session_state["pending_sql"] = payload["pending_sql"]
            st.warning("SQL approval required. Use the SQL Approval section below.")


def _sql_approval_section(base_url: str) -> None:
    st.subheader("5) SQL Approval")
    token = st.session_state.get("token")
    pending = st.session_state.get("pending_sql")

    if not token:
        st.info("Login first.")
        return
    if not pending:
        st.info("No pending SQL block yet. Ask a SQL-style question first.")
        return

    st.markdown("Pending SQL")
    st.code(pending.get("sql", ""), language="sql")
    st.caption(f"query_id: {pending.get('query_id', '')}")
    if pending.get("explanation"):
        st.write(f"Explanation: {pending.get('explanation')}")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("Approve & Execute"):
            status, payload = _request(
                "POST",
                base_url,
                "/query/sql/execute",
                token=token,
                json_body={"query_id": pending.get("query_id"), "approved": True},
            )
            _show_response(status, payload)
            if 200 <= status < 300:
                st.session_state.pop("pending_sql", None)
    with col_b:
        if st.button("Reject"):
            status, payload = _request(
                "POST",
                base_url,
                "/query/sql/execute",
                token=token,
                json_body={"query_id": pending.get("query_id"), "approved": False},
            )
            _show_response(status, payload)
            if 200 <= status < 300:
                st.session_state.pop("pending_sql", None)


def main() -> None:
    st.set_page_config(page_title="ADV RAG E2E Tester", layout="wide")
    st.title("ADV RAG - E2E Streamlit Tester")

    default_url = "http://localhost:8000"
    base_url = st.sidebar.text_input("API Base URL", value=default_url)
    st.sidebar.markdown("Swagger: `http://localhost:8000/docs`")
    st.sidebar.markdown("ReDoc: `http://localhost:8000/redoc`")

    _auth_section(base_url)
    st.divider()
    _health_section(base_url)
    st.divider()
    _upload_section(base_url)
    st.divider()
    _query_section(base_url)
    st.divider()
    _sql_approval_section(base_url)


if __name__ == "__main__":
    main()
