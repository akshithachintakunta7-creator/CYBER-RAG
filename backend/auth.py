import random
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from typing import Optional, Dict
import sqlite3
import hashlib
import os

from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr

from backend.config import (
    JWT_SECRET_KEY, JWT_ALGORITHM, JWT_EXPIRATION_MINUTES,
    SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM,
    ADMIN_EMAILS
)

# ---------- In-memory OTP store (for demo; use Redis in production) ----------
otp_store: Dict[str, dict] = {}  # email -> {"code": "123456", "expiry": timestamp}

# ---------- SQLite User Database ----------
DB_PATH = "users.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            is_admin INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    # Seed admin users from config
    for email in ADMIN_EMAILS:
        cursor.execute(
            "INSERT OR IGNORE INTO users (email, is_admin) VALUES (?, 1)",
            (email,)
        )
    conn.commit()
    conn.close()

init_db()

def get_user(email: str) -> Optional[dict]:
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT email, is_admin FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {"email": row[0], "is_admin": bool(row[1])}
    return None

def create_user(email: str, is_admin: bool = False):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT OR IGNORE INTO users (email, is_admin) VALUES (?, ?)",
        (email, 1 if is_admin else 0)
    )
    conn.commit()
    conn.close()

def generate_otp() -> str:
    return f"{random.randint(100000, 999999)}"

def send_otp_email(email: str, otp: str):
    """Send OTP via SMTP"""
    subject = "Your Cyber RAG Chatbot OTP"
    body = f"Your OTP for login is: {otp}\nIt expires in 5 minutes."
    
    msg = MIMEMultipart()
    msg["From"] = SMTP_FROM
    msg["To"] = email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    
    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        return True
    except Exception as e:
        print(f"❌ Email send error: {e}")
        return False

def request_otp(email: str):
    """Generate and send OTP; also ensure user exists (create if not)"""
    # Ensure user exists
    user = get_user(email)
    if not user:
        # Create user with admin flag if email is in ADMIN_EMAILS
        is_admin = email in ADMIN_EMAILS
        create_user(email, is_admin)
    
    # Generate and store OTP
    otp = generate_otp()
    expiry = time.time() + 300  # 5 minutes
    otp_store[email] = {"code": otp, "expiry": expiry}
    
    # Send email
    success = send_otp_email(email, otp)
    return success

def verify_otp(email: str, otp: str) -> Optional[str]:
    """Verify OTP; returns JWT token if successful"""
    record = otp_store.get(email)
    if not record:
        return None
    if record["code"] != otp:
        return None
    if time.time() > record["expiry"]:
        return None
    
    # OTP valid – clean it
    del otp_store[email]
    
    # Get user
    user = get_user(email)
    if not user:
        return None
    
    # Create JWT payload
    payload = {
        "sub": email,
        "is_admin": user["is_admin"],
        "exp": datetime.utcnow() + timedelta(minutes=JWT_EXPIRATION_MINUTES)
    }
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    return token

def verify_token(token: str) -> Optional[dict]:
    """Verify JWT token and return payload"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None