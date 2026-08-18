"""
CyberGuard AI – Modern Cybersecurity Chatbot (Light Theme)
"""

import streamlit as st
import requests
from datetime import datetime

# ============================================
# CONFIGURATION
# ============================================

import os
API_URL = os.getenv("API_URL", "http://backend:8000")
QUERY_URL = f"{API_URL}/query"
REQUEST_OTP_URL = f"{API_URL}/auth/request-otp"
VERIFY_OTP_URL = f"{API_URL}/auth/verify-otp"
UPLOAD_URL = f"{API_URL}/upload"

# ============================================
# PAGE CONFIG
# ============================================

st.set_page_config(
    page_title="CyberGuard AI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================
# CUSTOM CSS – Light Theme
# ============================================

st.markdown(
    """
<style>
    /* ---------- Global ---------- */
    .stApp {
        background: #f8fafc;
        color: #1e293b;
    }
    .main {
        padding: 0 2rem;
    }
    /* ---------- Sidebar ---------- */
    .css-1d391kg {
        background: #ffffff;
        border-right: 1px solid #e2e8f0;
    }
    .css-1d391kg .sidebar-content {
        padding: 1.5rem 1rem;
    }
    .sidebar-user {
        background: #f1f5f9;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1.5rem;
        border: 1px solid #e2e8f0;
        text-align: center;
    }
    .sidebar-user .email {
        font-weight: 600;
        color: #334155;
        font-size: 0.9rem;
        word-break: break-all;
    }
    .sidebar-user .badge {
        display: inline-block;
        background: #2563eb;
        color: #fff;
        font-size: 0.7rem;
        font-weight: 600;
        padding: 0.2rem 0.7rem;
        border-radius: 20px;
        margin-top: 0.3rem;
    }
    .sidebar-upload {
        background: #f1f5f9;
        border-radius: 12px;
        padding: 1rem;
        border: 1px solid #e2e8f0;
        margin-top: 1rem;
    }
    .sidebar-upload .title {
        color: #334155;
        font-weight: 600;
        font-size: 0.9rem;
        margin-bottom: 0.5rem;
    }
    .sidebar-caption {
        color: #94a3b8;
        font-size: 0.75rem;
        margin-top: 1.5rem;
        text-align: center;
    }
    /* ---------- Chat Containers ---------- */
    .chat-container {
        max-width: 900px;
        margin: 0 auto;
        padding: 2rem 0 6rem 0;
    }
    .chat-message {
        display: flex;
        align-items: flex-start;
        margin-bottom: 1.2rem;
        animation: fadeIn 0.3s ease-out;
    }
    .chat-message.user {
        flex-direction: row-reverse;
    }
    .chat-avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.2rem;
        flex-shrink: 0;
        margin: 0 0.8rem;
        background: #e2e8f0;
        border: 1px solid #e2e8f0;
    }
    .chat-avatar.user {
        background: #2563eb;
        border: none;
        color: #fff;
    }
    .chat-bubble {
        max-width: 80%;
        padding: 0.8rem 1.2rem;
        border-radius: 16px;
        background: #ffffff;
        border: 1px solid #e2e8f0;
        color: #1e293b;
        line-height: 1.6;
        word-wrap: break-word;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
    }
    .chat-bubble.user {
        background: #2563eb;
        border: none;
        color: #ffffff;
        box-shadow: 0 2px 4px rgba(37,99,235,0.2);
    }
    .chat-bubble .timestamp {
        font-size: 0.65rem;
        color: #94a3b8;
        margin-top: 0.3rem;
        text-align: right;
    }
    .chat-bubble.user .timestamp {
        color: rgba(255,255,255,0.7);
    }
    .source-item {
        background: #f8fafc;
        border-radius: 8px;
        padding: 0.6rem 0.8rem;
        margin: 0.4rem 0;
        border-left: 3px solid #2563eb;
        font-size: 0.85rem;
        color: #334155;
    }
    .source-item a {
        color: #2563eb;
        text-decoration: none;
    }
    .source-item a:hover {
        text-decoration: underline;
    }
    /* ---------- Input Area ---------- */
    .input-area {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        background: #ffffff;
        border-top: 1px solid #e2e8f0;
        padding: 0.8rem 2rem;
        backdrop-filter: blur(10px);
        z-index: 100;
    }
    .input-area .wrapper {
        max-width: 900px;
        margin: 0 auto;
        display: flex;
        gap: 0.8rem;
    }
    .input-area input {
        flex: 1;
        background: #f1f5f9;
        border: 1px solid #e2e8f0;
        border-radius: 30px;
        padding: 0.8rem 1.5rem;
        color: #1e293b;
        font-size: 1rem;
        outline: none;
        transition: border 0.2s;
    }
    .input-area input::placeholder {
        color: #94a3b8;
    }
    .input-area input:focus {
        border-color: #2563eb;
    }
    .input-area button {
        background: #2563eb;
        border: none;
        border-radius: 30px;
        padding: 0 2rem;
        color: #fff;
        font-weight: 600;
        cursor: pointer;
        transition: background 0.2s;
        font-size: 1rem;
        white-space: nowrap;
    }
    .input-area button:hover {
        background: #1d4ed8;
    }
    .input-area button:disabled {
        opacity: 0.5;
        cursor: not-allowed;
    }
    /* ---------- Animations ---------- */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    /* ---------- Responsive ---------- */
    @media (max-width: 768px) {
        .chat-bubble { max-width: 90%; }
        .input-area .wrapper { flex-direction: column; }
        .input-area button { width: 100%; }
        .chat-avatar { width: 32px; height: 32px; font-size: 1rem; }
    }
    /* ---------- Typing Indicator ---------- */
    .typing-indicator {
        display: inline-flex;
        align-items: center;
        gap: 4px;
        background: #f1f5f9;
        padding: 0.5rem 1rem;
        border-radius: 30px;
        color: #64748b;
    }
    .typing-indicator span {
        display: inline-block;
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #94a3b8;
        animation: pulse 1.4s infinite;
    }
    .typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
    .typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
    @keyframes pulse {
        0%, 80%, 100% { transform: scale(1); opacity: 0.6; }
        40% { transform: scale(1.4); opacity: 1; }
    }
    /* ---------- Login Page ---------- */
    .login-container {
        max-width: 420px;
        margin: 6rem auto;
        background: #ffffff;
        border-radius: 24px;
        padding: 2.5rem 2rem;
        border: 1px solid #e2e8f0;
        text-align: center;
        box-shadow: 0 4px 12px rgba(0,0,0,0.04);
    }
    .login-title {
        font-size: 2rem;
        font-weight: 700;
        color: #0f172a;
        margin-bottom: 0.5rem;
    }
    .login-sub {
        color: #64748b;
        margin-bottom: 2rem;
    }
    .login-container .stTextInput input {
        background: #f1f5f9;
        border: 1px solid #e2e8f0;
        color: #1e293b;
        border-radius: 30px;
        padding: 0.8rem 1.2rem;
    }
    .login-container .stButton button {
        background: #2563eb;
        border: none;
        border-radius: 30px;
        padding: 0.6rem 1.5rem;
        color: #fff;
        font-weight: 600;
        width: 100%;
    }
    .login-container .stButton button:hover {
        background: #1d4ed8;
    }
</style>
""",
    unsafe_allow_html=True,
)

# ============================================
# SESSION STATE
# ============================================

if "token" not in st.session_state:
    st.session_state.token = None
    st.session_state.user_email = None
    st.session_state.is_admin = False
    st.session_state.messages = []
    st.session_state.is_processing = False
    st.session_state.otp_sent = False
    st.session_state.otp_email = ""

# ============================================
# LOGIN PAGE
# ============================================

def login_page():
    st.markdown(
        f"""
        <div class="login-container">
            <div style="font-size:3rem;">🛡️</div>
            <div class="login-title">CyberGuard AI</div>
            <div class="login-sub">Secure • Intelligent • Confidential</div>
        """,
        unsafe_allow_html=True,
    )

    email = st.text_input("Email", key="login_email", placeholder="you@example.com")
    if st.button("Send OTP", key="send_otp"):
        if email:
            resp = requests.post(REQUEST_OTP_URL, json={"email": email})
            if resp.status_code == 200:
                st.session_state.otp_sent = True
                st.session_state.otp_email = email
                st.success("📨 OTP sent to your email")
            else:
                st.error("Failed to send OTP")

    if st.session_state.otp_sent:
        otp = st.text_input("Enter 6‑digit code", key="otp_input", placeholder="123456")
        if st.button("Verify", key="verify_otp"):
            resp = requests.post(
                VERIFY_OTP_URL,
                json={"email": st.session_state.otp_email, "otp": otp},
            )
            if resp.status_code == 200:
                data = resp.json()
                st.session_state.token = data["token"]
                st.session_state.user_email = st.session_state.otp_email
                st.session_state.is_admin = data.get("is_admin", False)
                st.session_state.otp_sent = False
                st.rerun()
            else:
                st.error("Invalid OTP")

    st.markdown("</div>", unsafe_allow_html=True)

# ============================================
# CHAT INTERFACE
# ============================================

def chat_interface():
    # ---------- Sidebar ----------
    with st.sidebar:
        st.markdown(
            f"""
            <div class="sidebar-user">
                <div class="email">👤 {st.session_state.user_email}</div>
                <div class="badge">{'🔑 Admin' if st.session_state.is_admin else 'User'}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("🚪 Logout", use_container_width=True):
            for key in ["token", "user_email", "is_admin", "messages"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

        st.markdown("---")

        if st.session_state.is_admin:
            st.markdown(
                """
                <div class="sidebar-upload">
                    <div class="title">📤 Admin Upload</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            uploaded_file = st.file_uploader("Upload PDF, TXT, or MD", type=["pdf", "txt", "md"])
            if uploaded_file and st.button("Upload to Knowledge Base", use_container_width=True):
                files = {"file": (uploaded_file.name, uploaded_file.getvalue())}
                resp = requests.post(
                    UPLOAD_URL,
                    files=files,
                    headers={"Authorization": f"Bearer {st.session_state.token}"},
                )
                if resp.status_code == 200:
                    data = resp.json()
                    st.success(f"✅ {data['chunks_created']} chunks added")
                else:
                    st.error(f"Upload failed: {resp.text}")

        st.markdown("---")
        st.markdown('<div class="sidebar-caption">🔒 End‑to‑end encrypted</div>', unsafe_allow_html=True)

    # ---------- Chat Header ----------
    st.markdown(
        """
        <div style="text-align:center; padding:1rem 0 1.5rem 0;">
            <span style="font-size:2.8rem;">🛡️</span>
            <h1 style="color:#0f172a; margin:0; font-weight:600;">CyberGuard AI</h1>
            <p style="color:#64748b; margin:0;">Your Intelligent Cybersecurity Assistant</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ---------- Chat History ----------
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.messages:
            if msg["role"] == "user":
                st.markdown(
                    f"""
                    <div class="chat-message user">
                        <div class="chat-avatar user">👤</div>
                        <div class="chat-bubble user">
                            {msg["content"]}
                            <div class="timestamp">{datetime.now().strftime("%I:%M %p")}</div>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                # Assistant message
                bubble = f"""
                    <div class="chat-message">
                        <div class="chat-avatar">🤖</div>
                        <div class="chat-bubble">
                            {msg["content"]}
                            <div class="timestamp">{datetime.now().strftime("%I:%M %p")}</div>
                        </div>
                    </div>
                """
                st.markdown(bubble, unsafe_allow_html=True)

                # Sources expander (if any)
                if "sources" in msg and msg["sources"]:
                    with st.expander("📚 View sources"):
                        for src in msg["sources"]:
                            if src.get("url"):
                                st.markdown(f"🔗 [{src.get('source', 'Link')}]({src.get('url')})")
                            else:
                                st.markdown(f"📄 {src.get('source', 'Document')}")
                            if src.get("text"):
                                st.caption(src["text"][:200] + "...")
                            st.divider()

        # Typing indicator
        if st.session_state.is_processing:
            st.markdown(
                """
                <div class="chat-message">
                    <div class="chat-avatar">🤖</div>
                    <div class="typing-indicator">
                        <span></span><span></span><span></span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ---------- Input Area ----------
    prompt = st.chat_input("Ask me anything about cybersecurity...")
    if prompt and not st.session_state.is_processing:
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.session_state.is_processing = True

        try:
            resp = requests.post(
                QUERY_URL,
                json={"query": prompt},
                headers={"Authorization": f"Bearer {st.session_state.token}"},
                timeout=120,
            )
            if resp.status_code == 200:
                data = resp.json()
                answer = data["response"]
                sources = data.get("sources", [])
                web_fallback = data.get("web_fallback", False)
                chunks_stored = data.get("chunks_stored", 0)

                msg_obj = {"role": "assistant", "content": answer, "sources": sources}
                st.session_state.messages.append(msg_obj)

                if web_fallback:
                    st.info(f"🌐 Web search used • {chunks_stored} new chunks stored")
                if data.get("timing"):
                    t = data["timing"]
                    st.caption(f"⏱️ {t['total']:.2f}s")
            else:
                error_msg = f"❌ Error: {resp.status_code}"
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
        except Exception as e:
            st.session_state.messages.append({"role": "assistant", "content": f"⚠️ Error: {str(e)}"})

        st.session_state.is_processing = False
        st.rerun()

# ============================================
# ROUTING
# ============================================

if not st.session_state.token:
    login_page()
else:
    chat_interface()