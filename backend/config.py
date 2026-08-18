"""
Configuration for RAG Pipeline
"""

import os
from dotenv import load_dotenv

load_dotenv()

# AWS S3 Vectors
VECTOR_BUCKET_NAME = os.getenv("VECTOR_BUCKET_NAME", "cyber-rag-embeddings")
INDEX_NAME = os.getenv("INDEX_NAME", "cyber-rag-vectors")
REGION = os.getenv("AWS_DEFAULT_REGION", "ap-south-2")

# Retrieval Settings
TOP_K_INITIAL = int(os.getenv("TOP_K_INITIAL", "25"))
TOP_K_FINAL = int(os.getenv("TOP_K_FINAL", "10"))
# Authentication
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "8897")
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_MINUTES = 60 * 24  # 1 day

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None
CACHE_TTL_SECONDS = int(os.getenv("CACHE_TTL_SECONDS", "3600").split('#')[0].strip())# 1 hour default
CACHE_ENABLED = os.getenv("CACHE_ENABLED", "True").lower() == "true"
# SMTP (for OTP)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER", "chintakuntaakshitha8@gmail.com")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "mlwq nkby wxnz tyeo")
SMTP_FROM = os.getenv("SMTP_FROM", "chintakuntaakshitha8@gmail.com")

# Admin emails (comma-separated)
ADMIN_EMAILS = os.getenv("ADMIN_EMAILS", "chintakuntaakshitha417@gmail.com").split(",")
ADMIN_EMAILS = [email.strip() for email in ADMIN_EMAILS]
# Groq API
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "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")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
# Web Search Settings
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "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")
WEB_SEARCH_ENABLED = os.getenv("WEB_SEARCH_ENABLED", "True").lower() == "true"
WEB_SEARCH_FALLBACK_THRESHOLD = float(os.getenv("WEB_SEARCH_FALLBACK_THRESHOLD", "0.4"))
MAX_WEB_RESULTS = int(os.getenv("MAX_WEB_RESULTS", "3"))
# Embedding Model
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

RERANKER_MODEL = os.getenv("RERANKER_MODEL", "BAAI/bge-reranker-v2-m3")  # Smaller, faster, less memory
# RERANKER_MODEL = "BAAI/bge-reranker-v2-m3"  # Full model - use if you have 8GB+ RAM