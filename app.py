import streamlit as st
import requests

API_URL = "http://localhost:8000"

st.set_page_config(page_title="GuardRail RAG", page_icon="🛡️", layout="centered")

st.markdown("""
<style>
.main-header {
    text-align: center;
    padding: 1rem 0 0.5rem 0;
}
.main-header h1 {
    font-size: 2.2rem;
    margin-bottom: 0;
}
.main-header p {
    color: #888;
    font-size: 0.95rem;
}
.badge {
    display: inline-block;
    padding: 0.2rem 0.65rem;
    border-radius: 12px;
    font-size: 0.78rem;
    font-weight: 600;
    margin-right: 0.4rem;
}
.badge-role {
    background: rgba(99, 102, 241, 0.15);
    color: #818cf8;
    border: 1px solid rgba(99, 102, 241, 0.4);
}
.badge-source {
    background: rgba(148, 163, 184, 0.15);
    color: #cbd5e1;
    border: 1px solid rgba(148, 163, 184, 0.3);
}
.badge-redacted {
    background: rgba(234, 179, 8, 0.15);
    color: #eab308;
    border: 1px solid rgba(234, 179, 8, 0.4);
}
.badge-clean {
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
    border: 1px solid rgba(34, 197, 94, 0.4);
}
.badge-passed {
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
    border: 1px solid rgba(34, 197, 94, 0.4);
}
.badge-flagged {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.4);
}
.meta-row {
    margin-top: 0.5rem;
    padding-top: 0.5rem;
    border-top: 1px solid rgba(255,255,255,0.08);
}
.blocked-box {
    background: rgba(239, 68, 68, 0.08);
    border-left: 3px solid #ef4444;
    border-radius: 0 8px 8px 0;
    padding: 0.75rem 1rem;
    margin: 0.5rem 0;
}
</style>
""", unsafe_allow_html=True)

if "token" not in st.session_state:
    st.session_state.token = None
if "role" not in st.session_state:
    st.session_state.role = None
if "username" not in st.session_state:
    st.session_state.username = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []


def logout():
    st.session_state.token = None
    st.session_state.role = None
    st.session_state.username = None
    st.session_state.chat_history = []


def render_meta(data):
    source = data.get("source") or "None"
    redacted = data.get("redacted_count", 0)
    guardrail = data.get("guardrail_status", "n/a")

    redacted_badge = (
        f'<span class="badge badge-redacted">🔒 {redacted} PII redacted</span>'
        if redacted > 0
        else '<span class="badge badge-clean">✓ No PII found</span>'
    )
    guardrail_badge = (
        f'<span class="badge badge-passed">✓ Guardrail passed</span>'
        if guardrail == "passed"
        else f'<span class="badge badge-flagged">⚠ Guardrail: {guardrail}</span>'
    )

    st.markdown(
        f"""
        <div class="meta-row">
            <span class="badge badge-source">📄 {source}</span>
            {redacted_badge}
            {guardrail_badge}
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_login():
    st.markdown(
        """
        <div class="main-header">
            <h1>🛡️ GuardRail RAG</h1>
            <p>Secure retrieval-augmented generation with RBAC, PII redaction & output validation</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    _, col, _ = st.columns([1, 2, 1])
    with col:
        with st.form("login_form"):
            username = st.text_input("Username")
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Log in", use_container_width=True)

        if submitted:
            try:
                response = requests.post(
                    f"{API_URL}/login",
                    json={"username": username, "password": password},
                    timeout=10,
                )
                if response.status_code == 200:
                    data = response.json()
                    st.session_state.token = data["access_token"]
                    st.session_state.role = data["role"]
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("Invalid username or password.")
            except requests.exceptions.ConnectionError:
                st.error("Cannot reach the backend. Is `uvicorn main:app --reload` running?")

        st.caption("Demo accounts (password: `password123`): **carol** (intern) · **bob** (employee) · **admin**")


def show_chat():
    with st.sidebar:
        st.markdown("### 🛡️ GuardRail RAG")
        st.markdown("---")
        st.markdown(f"**{st.session_state.username}**")
        st.markdown(f'<span class="badge badge-role">{st.session_state.role}</span>', unsafe_allow_html=True)
        st.markdown("---")
        st.caption("**Security pipeline**")
        st.caption("① RBAC filtering")
        st.caption("② PII redaction")
        st.caption("③ Output validation")
        st.markdown("---")
        if st.button("Log out", use_container_width=True):
            logout()
            st.rerun()

    st.markdown(
        """
        <div class="main-header">
            <h1>🛡️ GuardRail RAG</h1>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for entry in st.session_state.chat_history:
        with st.chat_message("user"):
            st.write(entry["question"])
        with st.chat_message("assistant"):
            if entry.get("blocked"):
                st.markdown(
                    f'<div class="blocked-box">🚫 <b>Access restricted</b><br>{entry["answer"]}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.write(entry["answer"])
                render_meta(entry)

    question = st.chat_input("Ask a question...")
    if question:
        with st.chat_message("user"):
            st.write(question)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    headers = {"Authorization": f"Bearer {st.session_state.token}"}
                    response = requests.post(
                        f"{API_URL}/query",
                        json={"question": question},
                        headers=headers,
                        timeout=120,
                    )
                    if response.status_code == 200:
                        data = response.json()
                        is_blocked = data.get("access_denied", False)

                        if is_blocked:
                            st.markdown(
                                f'<div class="blocked-box">🚫 <b>Access restricted</b><br>{data["answer"]}</div>',
                                unsafe_allow_html=True,
                            )
                        else:
                            st.write(data["answer"])
                            render_meta(data)

                        st.session_state.chat_history.append(
                            {
                                "question": question,
                                "answer": data["answer"],
                                "source": data.get("source"),
                                "redacted_count": data.get("redacted_count"),
                                "guardrail_status": data.get("guardrail_status"),
                                "blocked": is_blocked,
                            }
                        )
                    elif response.status_code == 401:
                        st.error("Session expired. Please log out and log in again.")
                    else:
                        st.error(f"Error: {response.status_code}")
                except requests.exceptions.ConnectionError:
                    st.error("Cannot reach the backend. Is `uvicorn main:app --reload` running?")


if st.session_state.token:
    show_chat()
else:
    show_login()