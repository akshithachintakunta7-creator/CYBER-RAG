 CyberGuard AI – Cybersecurity RAG Chatbot

## 🛡️ A Production-Grade Retrieval-Augmented Generation (RAG) System for Cybersecurity

---

## 📌 Table of Contents

1. [Overview](#overview)
2. [Features](#features)
3. [System Architecture](#system-architecture)
4. [Technology Stack](#technology-stack)
5. [RAG Pipeline Flow](#rag-pipeline-flow)
6. [Installation & Setup](#installation--setup)
7. [AWS EC2 Deployment](#aws-ec2-deployment)
8. [API Endpoints](#api-endpoints)
9. [Environment Variables](#environment-variables)
10. [Performance Metrics](#performance-metrics)
11. [Challenges & Solutions](#challenges--solutions)
12. [Project Structure](#project-structure)
13. [Docker Hub Images](#docker-hub-images)
14. [Contributing](#contributing)
15. [License](#license)
16. [Acknowledgments](#acknowledgments)

---

## 📖 Overview

**CyberGuard AI** is a production‑ready, Retrieval‑Augmented Generation (RAG) based cybersecurity assistant that combines semantic search, large language models, and continuous learning capabilities. The system processes cybersecurity documents, generates semantic embeddings, and provides context‑aware, conversational responses to user queries through an intuitive chat interface.

### 🎯 Key Achievements

| Metric | Value |
|--------|-------|
| **Document Chunks Indexed** | 400,953 |
| **Faithfulness Score (RAGAS)** | 0.971 |
| **Retrieval Latency (FAISS)** | 5‑20 ms |
| **Cache Hit Rate** | 65% |
| **Average Response Time** | 2‑5 s |
| **Cached Response Time** | < 300 ms |

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| 🔐 **Secure Authentication** | Email‑based OTP login with JWT tokens |
| 🧠 **Semantic Search** | Meaning‑based retrieval using sentence‑transformers |
| 🚀 **FAISS Acceleration** | Sub‑20ms vector search with HNSW indexing |
| 📚 **Document Upload** | Admin‑only PDF/TXT/MD upload with auto‑chunking |
| 🌐 **Web Search Fallback** | Self‑learning via Tavily API for out‑of‑knowledge queries |
| ⚡ **Redis Cache** | 65% cache hit rate with sub‑second responses |
| 🎯 **BGE Reranking** | 10‑15% retrieval accuracy improvement |
| 🤖 **Groq LLM Integration** | Llama 3.3 70B for high‑quality responses |
| 📊 **Source Citations** | Transparent sources with page references |
| 🐳 **Dockerized** | One‑click deployment on any platform |
| ☁️ **AWS EC2 Ready** | Production deployment guide included |

---

## 🏗️ System Architecture

### High‑Level Architecture
┌─────────────────────────────────────────────────────────────┐
│ FRONTEND (Streamlit) │
│ ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐ │
│ │ Login │ │ Chat │ │ Admin Upload │ │
│ └──────────────┘ └──────────────┘ └──────────────────┘ │
└───────────────────────────┬─────────────────────────────────┘
│ HTTP REST API
┌───────────────────────────▼─────────────────────────────────┐
│ BACKEND (FastAPI) │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ Authentication │ Query Processing │ Admin │ │
│ │ (JWT/OTP) │ (RAG Pipeline) │ Routes │ │
│ └─────────────────────────────────────────────────────────┘ │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │
│ │ Web Search │ │ Cache │ │ Document Processor │ │
│ │ (Tavily) │ │ (Redis) │ │ (Chunking/Embed) │ │
│ └─────────────┘ └─────────────┘ └─────────────────────┘ │
└───────────────────────────┬─────────────────────────────────┘
│
┌───────────────────────────▼─────────────────────────────────┐
│ EXTERNAL SERVICES │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │
│ │ S3 Vectors │ │ Groq API │ │ Tavily API │ │
│ │ / FAISS │ │ (LLM) │ │ (Web Search) │ │
│ └─────────────┘ └─────────────┘ └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘

text

### RAG Pipeline Flow
User Query
│
▼
┌─────────────────────────────────────────────────────────────┐
│ CACHE CHECK (Redis) │
└───────────────────────────┬─────────────────────────────────┘
│
┌─────────────┴─────────────┐
│ HIT │ MISS
▼ ▼
┌─────────────────────┐ ┌─────────────────────────────────┐
│ Return Cached │ │ EMBEDDING GENERATION │
│ Response (Instant) │ │ Sentence-Transformer │
└─────────────────────┘ │ all-MiniLM-L6-v2 (384 dims) │
└─────────────┬───────────────────┘
▼
┌─────────────────────────────────┐
│ VECTOR SEARCH │
│ ┌──────────┐ ┌──────────────┐ │
│ │ FAISS │ │ S3 Vectors │ │
│ │ (5-20ms) │ │ (300-500ms) │ │
│ └──────────┘ └──────────────┘ │
└─────────────┬───────────────────┘
▼
┌─────────────────────────────────┐
│ RELEVANCE CHECK │
│ Top Score < Threshold (0.4)? │
└─────────────┬───────────────────┘
│
┌─────────────┴─────────────┐
│ HIGH │ LOW
▼ ▼
┌─────────────────────┐ ┌─────────────────────┐
│ RERANK (BGE) │ │ WEB SEARCH │
│ Cross-Encoder │ │ (Tavily API) │
│ Batch: 16 │ │ Fetch & Extract │
└──────────┬──────────┘ └──────────┬──────────┘
│ │
│ ┌─────────────────────┐
│ │ CHUNK & STORE │
│ │ Semantic Chunking │
│ │ Embed & Store │
│ └─────────────────────┘
│ │
└─────────────┬────────────┘
▼
┌─────────────────────────────────┐
│ CONTEXT ASSEMBLY │
│ Top-K Chunks (5) │
│ Build Context with Sources │
└─────────────┬───────────────────┘
▼
┌─────────────────────────────────┐
│ LLM GENERATION │
│ Groq Llama 3.3 70B │
│ Temperature: 0.3 │
│ Max Tokens: 1024 │
└─────────────┬───────────────────┘
▼
┌─────────────────────────────────┐
│ CACHE & RETURN │
│ Store in Redis (TTL: 1 hour) │
│ Return with Sources & Timing │
└─────────────────────────────────┘

text

---

## 🛠️ Technology Stack

### Backend

| Library | Version | Purpose |
|---------|---------|---------|
| FastAPI | 0.104.1 | Web framework |
| Uvicorn | 0.24.0 | ASGI server |
| sentence‑transformers | 2.5.0 | Embedding generation |
| transformers | 4.38.0 | BGE reranker |
| torch | 2.0.0+ | PyTorch backend |
| faiss‑cpu | 1.7.0+ | Fast vector search |
| groq | 0.8.0+ | Groq API client |
| boto3 | 1.35.0+ | AWS S3 Vectors |
| redis | 5.0.0 | Cache client |
| tavily‑python | Latest | Web search |

### Frontend

| Technology | Purpose |
|------------|---------|
| Streamlit 1.29.0 | UI framework |
| requests | API client |
| python‑dotenv | Environment management |

### Infrastructure

| Component | Technology |
|-----------|------------|
| Containerization | Docker |
| Container Registry | Docker Hub |
| Orchestration | Docker Compose |
| Cloud Provider | AWS EC2 |
| Vector Database | S3 Vectors / FAISS |
| LLM | Groq Llama 3.3 70B |
| Web Search | Tavily API |
| Cache | Redis |

---

## 📡 API Endpoints

| Method | Endpoint | Description | Auth |
|--------|----------|-------------|------|
| POST | `/auth/request-otp` | Request OTP | ❌ |
| POST | `/auth/verify-otp` | Verify OTP & get JWT | ❌ |
| POST | `/query` | Process RAG query | ✅ |
| GET | `/health` | Health check | ❌ |
| GET | `/stats` | System statistics | ❌ |
| POST | `/upload` | Upload document (Admin only) | ✅ |
| GET | `/admin/users` | List users (Admin only) | ✅ |
| POST | `/admin/block-user` | Block user (Admin only) | ✅ |
| POST | `/admin/unblock-user` | Unblock user (Admin only) | ✅ |
| GET | `/admin/comments` | View flagged comments (Admin only) | ✅ |

---

## 🚀 Installation & Setup

### Prerequisites

- Python 3.11+
- Docker & Docker Compose (for containerized deployment)
- AWS Account (for S3 Vectors)
- Groq API Key
- Tavily API Key (optional, for web search)

### Step 1: Clone the Repository

```bash
git clone https://github.com/your-username/cyber-rag.git
cd cyber-rag
Step 2: Create Environment File
bash
cp .env.template .env
# Edit .env with your credentials
Step 3: Build and Run with Docker Compose
bash
docker compose pull
docker compose up -d
Step 4: Access the Application
Frontend: http://localhost:8501

Backend API Docs: http://localhost:8000/docs

☁️ AWS EC2 Deployment
Infrastructure Requirements
Component	Specification
AMI	Ubuntu 22.04 LTS
Instance Type	t3.medium (min), t3.large (recommended)
Storage	50 GB gp3
Security Group	Ports: 22, 8501, 8000
Step-by-Step Deployment
1. Launch EC2 Instance
bash
# In AWS Console:
# EC2 Dashboard → Launch Instance
# Choose Ubuntu 22.04 LTS
# Select t3.large
# Configure security group with ports 22, 8501, 8000
# Create/download key pair
2. Connect to EC2
bash
ssh -i your-key.pem ubuntu@<EC2_PUBLIC_IP>
3. Install Docker & Compose
bash
sudo apt update
sudo apt install docker.io docker-compose-v2 -y
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker ubuntu
newgrp docker
4. Transfer Files
bash
# From local machine:
scp -i your-key.pem docker-compose.yml ubuntu@<EC2_IP>:/home/ubuntu/
scp -i your-key.pem .env ubuntu@<EC2_IP>:/home/ubuntu/
scp -i your-key.pem faiss_index.bin ubuntu@<EC2_IP>:/home/ubuntu/   # optional
5. Deploy
bash
cd /home/ubuntu
docker compose pull
docker compose up -d
6. Verify
bash
docker compose ps
docker compose logs backend | grep -i "faiss"
7. Access
Frontend: http://<EC2_PUBLIC_IP>:8501

Backend API: http://<EC2_PUBLIC_IP>:8000/docs

🔐 Environment Variables
Variable	Required	Description
GROQ_API_KEY	✅	Groq API key
AWS_ACCESS_KEY_ID	✅	AWS access key
AWS_SECRET_ACCESS_KEY	✅	AWS secret key
AWS_DEFAULT_REGION	✅	AWS region
VECTOR_BUCKET_NAME	✅	S3 Vectors bucket name
INDEX_NAME	✅	S3 Vectors index name
TAVILY_API_KEY	❌	Tavily web search API key
SMTP_HOST	❌	SMTP server for OTP
SMTP_PORT	❌	SMTP port
SMTP_USER	❌	SMTP username
SMTP_PASSWORD	❌	SMTP password (app password)
SMTP_FROM	❌	From email address
ADMIN_EMAILS	❌	Comma-separated admin emails
JWT_SECRET_KEY	✅	JWT signing secret
REDIS_HOST	✅	Redis hostname
REDIS_PORT	✅	Redis port
CACHE_ENABLED	✅	Enable/disable Redis cache
CACHE_TTL_SECONDS	✅	Cache TTL in seconds
WEB_SEARCH_ENABLED	❌	Enable web search fallback
WEB_SEARCH_FALLBACK_THRESHOLD	❌	Relevance threshold for web search
📊 Performance Metrics
RAGAS Evaluation
Metric	Score	Interpretation
Faithfulness	0.971	Answer grounded in context
Answer Relevancy	0.714	Directly addresses question
Context Relevancy	0.686	Retrieved context relevant
Answer Completeness	0.662	Coverage of ground truth
System Performance
Metric	Value	Description
Total Vectors	400,953	Number of indexed chunks
Embedding Dimension	384	all-MiniLM-L6-v2 dimension
FAISS Index Size	659 MB	HNSW index with 32 neighbors
Retrieval Latency (FAISS)	5‑20 ms	Sub‑millisecond search
Retrieval Latency (S3)	300‑500 ms	Fallback option
Average Response Time	2‑5 s	Complete pipeline
Cache Hit Rate	65%	Redis cache efficiency
Cache Response Time	< 300 ms	Instant response
🧩 Challenges & Solutions
Challenge	Solution
Hugging Face cache permission	Added HOME, TRANSFORMERS_CACHE, HF_HOME environment variables
Redis authentication error	Set REDIS_PASSWORD = os.getenv("REDIS_PASSWORD") or None
Frontend connection refused	Used API_URL = os.getenv("API_URL", "http://backend:8000")
Docker build timeout	Split requirements.txt into backend/frontend‑specific files
FAISS memory error	Built index directly from embeddings.npy (616 MB) instead of JSON
Web search not triggering	Lowered WEB_SEARCH_FALLBACK_THRESHOLD to 0.4
High S3 latency	Integrated FAISS (300‑500ms → 5‑20ms)
Login widgets persisted after login	Added guard clause in login_page()
📁 Project Structure
text
cyber-rag/
├── backend/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── rag_pipeline.py      # RAG logic
│   ├── auth.py              # Authentication
│   ├── web_search.py        # Web search module
│   ├── cache.py             # Redis cache
│   ├── config.py            # Configuration
│   └── semantic_chunking_embedding.py
├── frontend/
│   └── streamlit_app.py     # Streamlit UI
├── docker/
│   ├── backend.Dockerfile
│   └── frontend.Dockerfile
├── docker-compose.yml
├── requirements-backend.txt
├── requirements-frontend.txt
├── .env
├── faiss_index.bin          # FAISS index (optional)
└── README.md
🐳 Docker Hub Images
Image	Pull Command
Backend	docker pull aksshh/rag-backend:latest
Frontend	docker pull aksshh/rag-frontend:latest
Quick Start
bash
# Pull and run
docker compose pull
docker compose up -d
👥 Contributing
Contributions are welcome! Please follow these steps:

Fork the repository.

Create a feature branch (git checkout -b feature/amazing-feature).

Commit your changes (git commit -m 'Add amazing feature').

Push to the branch (git push origin feature/amazing-feature).

Open a Pull Request.

📄 License
This project is for educational and research purposes. All rights reserved.

🙏 Acknowledgments
Groq for the Llama 3.3 70B API

AWS for S3 Vectors

Tavily for web search capabilities

Hugging Face for sentence-transformers and BGE models

FAISS for fast vector search

Redis for caching

Streamlit for the frontend framework

FastAPI for the backend framework

