"""
FastAPI Backend for RAG Chatbot - Clean & Professional
"""

from fastapi import FastAPI, HTTPException, Depends, Header, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr
from typing import List, Dict, Any, Optional
import os
import tempfile
import hashlib
from dotenv import load_dotenv

load_dotenv()

from backend.auth import request_otp, verify_otp, verify_token, get_user
from backend.rag_pipeline import rag_pipeline
from backend.config import TOP_K_INITIAL, TOP_K_FINAL, VECTOR_BUCKET_NAME, INDEX_NAME
from backend.semantic_chunking_embedding import EmbeddingSemanticChunker

# ============================================
# FASTAPI APP
# ============================================

app = FastAPI(
    title="Cybersecurity RAG Chatbot API",
    description="AI-powered cybersecurity assistant with BGE Reranker",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================
# DEPENDENCIES
# ============================================

def get_current_user(authorization: str = Header(..., alias="Authorization")):
    """
    Expects header: Authorization: Bearer <jwt-token>
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid token format")
    token = authorization.split(" ")[1]
    payload = verify_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload

def admin_required(payload: dict = Depends(get_current_user)):
    if not payload.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return payload

# ============================================
# PYDANTIC MODELS
# ============================================

class OTPRequest(BaseModel):
    email: EmailStr

class OTPVerify(BaseModel):
    email: EmailStr
    otp: str

class QueryRequest(BaseModel):
    query: str
    top_k: Optional[int] = 5

class SourceInfo(BaseModel):
    source: str
    page: str
    text: str

class QueryResponse(BaseModel):
    query: str
    response: str
    sources: List[SourceInfo]
    retrieved_count: int
    timing: Dict[str, float]
    web_fallback: bool = False
    chunks_stored: int = 0

class HealthResponse(BaseModel):
    status: str
    message: str

class UploadResponse(BaseModel):
    message: str
    chunks_created: int
    filename: str

# ============================================
# VALIDATION EXCEPTION HANDLER (debugging)
# ============================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc):
    print("❌ Validation errors:")
    for error in exc.errors():
        print(f"  - {error}")
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()}
    )

# ============================================
# AUTH ENDPOINTS
# ============================================

@app.post("/auth/request-otp")
async def request_otp_endpoint(req: OTPRequest):
    success = request_otp(req.email)
    if success:
        return {"message": "OTP sent to your email"}
    else:
        raise HTTPException(status_code=500, detail="Failed to send OTP")

@app.post("/auth/verify-otp")
async def verify_otp_endpoint(req: OTPVerify):
    token = verify_otp(req.email, req.otp)
    if token:
        user = get_user(req.email)
        return {"token": token, "is_admin": user["is_admin"] if user else False}
    else:
        raise HTTPException(status_code=401, detail="Invalid or expired OTP")

# ============================================
# MAIN ENDPOINTS
# ============================================

@app.get("/", response_model=Dict[str, str])
async def root():
    return {"message": "Cybersecurity RAG Chatbot API", "status": "running"}

@app.get("/health", response_model=HealthResponse)
async def health_check():
    try:
        rag_pipeline.s3vectors.list_indexes(vectorBucketName=VECTOR_BUCKET_NAME)
        return HealthResponse(status="healthy", message="All systems operational")
    except Exception:
        return HealthResponse(status="degraded", message="Service unavailable")

@app.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest, payload: dict = Depends(get_current_user)):
    if not request.query or len(request.query.strip()) < 2:
        raise HTTPException(status_code=400, detail="Please enter a valid question.")
    try:
        results = rag_pipeline.process_query(request.query)
        return QueryResponse(
            query=results["query"],
            response=results["response"],
            sources=results["sources"],
            retrieved_count=results["retrieved_count"],
            timing=results["timing"],
            web_fallback=results.get("web_fallback", False),
            chunks_stored=results.get("chunks_stored", 0)
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/stats")
async def get_stats():
    return {
        "status": "ready",
        "model": "AI Assistant with BGE Reranker",
        "reranker": "Enabled",
        "top_k_initial": TOP_K_INITIAL,
        "top_k_final": TOP_K_FINAL,
    }

# ============================================
# ADMIN UPLOAD
# ============================================

@app.post("/upload", response_model=UploadResponse)
async def upload_document(
    file: UploadFile = File(...),
    admin: dict = Depends(admin_required)
):
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in [".pdf", ".txt", ".md"]:
        raise HTTPException(status_code=400, detail="Only PDF, TXT, MD allowed")
    contents = await file.read()
    if len(contents) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File > 50 MB")
    
    with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
        tmp.write(contents)
        tmp_path = tmp.name

    try:
        if ext == ".pdf":
            import PyPDF2
            with open(tmp_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                text = "".join(page.extract_text() or "" for page in reader.pages)
        else:
            with open(tmp_path, "r", encoding="utf-8") as f:
                text = f.read()

        if not text or len(text.strip()) < 50:
            raise HTTPException(status_code=400, detail="Not enough text extracted")

        chunker = EmbeddingSemanticChunker(
            embedding_model="all-MiniLM-L6-v2",
            similarity_threshold=0.65,
            min_chunk_tokens=200,
            max_chunk_tokens=800,
            overlap_tokens=80
        )
        chunks = chunker.chunk_text(text, source=f"upload_{file.filename}")
        if not chunks:
            raise HTTPException(status_code=400, detail="Chunking failed")

        stored_count = 0
        for chunk in chunks:
            embedding = rag_pipeline.embedding_model.encode(chunk.text, normalize_embeddings=True)
            vector_key = f"upload_{hashlib.md5(chunk.text.encode()).hexdigest()[:12]}"
            rag_pipeline.s3vectors.put_vectors(
                vectorBucketName=VECTOR_BUCKET_NAME,
                indexName=INDEX_NAME,
                vectors=[{
                    "key": vector_key,
                    "data": {"float32": embedding.tolist()},
                    "metadata": {
                        "source_pdf": f"upload_{file.filename}",
                        "chunk_id": chunk.chunk_id,
                        "text": chunk.text[:300],
                        "uploaded_by": admin.get("sub", "admin")
                    }
                }]
            )
            stored_count += 1
        return UploadResponse(
            message=f"Uploaded {file.filename}",
            chunks_created=stored_count,
            filename=file.filename
        )
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
    )