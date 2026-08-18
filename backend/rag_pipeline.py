"""
RAG Pipeline: S3 Vectors + BGE Reranker + Groq LLM + Web Search Fallback + Redis Cache
"""

import boto3
import json
import numpy as np
import time
from typing import List, Dict, Any
from sentence_transformers import SentenceTransformer
from groq import Groq
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import gc
import os

# Import from config
from backend.config import (
    VECTOR_BUCKET_NAME,
    INDEX_NAME,
    REGION,
    GROQ_API_KEY,
    GROQ_MODEL,
    EMBEDDING_MODEL,
    TOP_K_INITIAL,
    TOP_K_FINAL,
    RERANKER_MODEL,
    WEB_SEARCH_ENABLED,
    WEB_SEARCH_FALLBACK_THRESHOLD,
)

# Web search module
from backend.web_search import process_web_content

# Redis cache
from backend.cache import cache

# ============================================
# RERANKER LOADING WITH FALLBACK
# ============================================

def load_reranker(model_name):
    """Load reranker with fallback options"""
    try:
        print(f"  - Attempting to load: {model_name}")
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name)
        model.eval()
        return tokenizer, model
    except Exception as e:
        print(f"  ⚠️ Failed to load {model_name}: {e}")
        # Try fallback to mini version
        if model_name == "BAAI/bge-reranker-v2-m3":
            try:
                print("  - Trying fallback: BAAI/bge-reranker-v2-mini...")
                tokenizer = AutoTokenizer.from_pretrained("BAAI/bge-reranker-v2-mini")
                model = AutoModelForSequenceClassification.from_pretrained("BAAI/bge-reranker-v2-mini")
                model.eval()
                print("  ✅ Loaded fallback reranker (mini)")
                return tokenizer, model
            except Exception as e2:
                print(f"  ❌ Fallback also failed: {e2}")
                raise
        else:
            raise

# ============================================
# INITIALIZE COMPONENTS (Singleton Pattern)
# ============================================

class RAGPipeline:
    _instance = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(RAGPipeline, cls).__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        
        print("📚 Initializing RAG Pipeline...")
        
        # 1. Embedding Model
        print("  - Loading embedding model...")
        self.embedding_model = SentenceTransformer(EMBEDDING_MODEL)
        
        # 2. S3 Vectors Client
        print("  - Connecting to S3 Vectors...")
        self.s3vectors = boto3.client('s3vectors', region_name=REGION)
        
        # 3. BGE Reranker
        print("  - Loading BGE Reranker (this may take a moment)...")
        try:
            self.reranker_tokenizer, self.reranker_model = load_reranker(RERANKER_MODEL)
            self.device = "cpu"
            self.reranker_model.to(self.device)
            print(f"  ✅ BGE Reranker loaded successfully!")
        except Exception as e:
            print(f"  ❌ Failed to load BGE Reranker: {e}")
            print("  ⚠️ Reranker is critical for production.")
            raise
        
        # 4. Groq LLM
        print("  - Initializing Groq client...")
        if not GROQ_API_KEY:
            print("  ⚠️ WARNING: GROQ_API_KEY not set in environment variables!")
        self.groq_client = Groq(api_key=GROQ_API_KEY)
        
        print("✅ Pipeline initialized! (Reranker: Enabled)\n")
    
    def retrieve_from_s3(self, query: str, top_k: int = None) -> List[Dict]:
        """Retrieve top-k chunks from S3 Vectors"""
        if top_k is None:
            top_k = TOP_K_INITIAL
            
        try:
            query_embedding = self.embedding_model.encode(query, normalize_embeddings=True)
            
            response = self.s3vectors.query_vectors(
                vectorBucketName=VECTOR_BUCKET_NAME,
                indexName=INDEX_NAME,
                queryVector={"float32": query_embedding.tolist()},
                topK=top_k,
                returnDistance=True,
                returnMetadata=True
            )
            
            return response.get('vectors', [])
        except Exception as e:
            print(f"❌ Error retrieving from S3: {e}")
            return []
    
    def rerank_with_bge(self, query: str, documents: List[Dict]) -> List[Dict]:
        """Rerank documents using BGE Reranker"""
        if not documents:
            return []
        
        # If few documents, skip reranking
        if len(documents) <= TOP_K_FINAL:
            for doc in documents:
                distance = doc.get('distance', 0.5)
                doc['rerank_score'] = 1 - distance
            return documents
        
        # Prepare pairs
        pairs = []
        valid_docs = []
        
        for doc in documents:
            metadata = doc.get('metadata', {})
            text = metadata.get('text', '')
            if not text:
                text = f"Document {doc.get('key', 'unknown')}"
            if len(text.strip()) > 10:
                pairs.append((query, text))
                valid_docs.append(doc)
        
        if not pairs:
            for doc in documents:
                distance = doc.get('distance', 0.5)
                doc['rerank_score'] = 1 - distance
            return documents
        
        try:
            # Process in batches
            batch_size = 16
            all_scores = []
            
            for i in range(0, len(pairs), batch_size):
                batch_pairs = pairs[i:i+batch_size]
                
                inputs = self.reranker_tokenizer(
                    batch_pairs,
                    padding=True,
                    truncation=True,
                    return_tensors='pt',
                    max_length=256
                )
                
                inputs = {k: v.to(self.device) for k, v in inputs.items()}
                
                with torch.no_grad():
                    scores = self.reranker_model(**inputs, return_dict=True).logits.view(-1,).float()
                
                all_scores.extend(scores.cpu().numpy().tolist())
                
                # Cleanup
                del inputs
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                gc.collect()
            
            # Add scores
            for doc, score in zip(valid_docs, all_scores):
                doc['rerank_score'] = float(score)
            
            sorted_docs = sorted(valid_docs, key=lambda x: x.get('rerank_score', 0), reverse=True)
            
            return sorted_docs
            
        except Exception as e:
            print(f"❌ Error during reranking: {e}")
            for doc in documents:
                distance = doc.get('distance', 0.5)
                doc['rerank_score'] = 1 - distance
            return sorted(documents, key=lambda x: x.get('rerank_score', 0), reverse=True)
    
    def generate_with_groq(self, query: str, context: str) -> str:
        """Generate answer using Groq LLM"""
        system_prompt = """You are a cybersecurity expert assistant. Provide accurate, helpful responses based on the given context. If the context doesn't contain enough information, acknowledge this and provide general guidance if possible."""
        
        user_prompt = f"""Based on the following context, answer the question.

Context:
{context}

Question: {query}

Answer:"""
        
        try:
            response = self.groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,
                max_tokens=1024,
                top_p=0.9
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error generating response: {str(e)}"
    
    def _get_top_score(self, retrieved: List[Dict]) -> float:
        """Compute the highest similarity score from retrieved chunks."""
        if not retrieved:
            return 0.0
        scores = [1 - doc.get('distance', 0.5) for doc in retrieved]
        return max(scores)
    
    def process_query(self, query: str) -> Dict[str, Any]:
        """
        Complete RAG pipeline: Cache → Retrieve → Check Relevance → (Fallback to Web) → Rerank → Generate.
        """
        # 1️⃣ Check cache
        cached = cache.get(query)
        if cached:
            print(f"✅ Cache hit for: {query[:50]}...")
            return cached

        start_time = time.time()
        
        # Step 1: Retrieve
        retrieve_start = time.time()
        retrieved = self.retrieve_from_s3(query)
        retrieve_time = time.time() - retrieve_start
        
        # Step 2: Check relevance for fallback
        top_score = self._get_top_score(retrieved)
        print(f"📊 Top retrieval score: {top_score:.3f}")
        
        # If low relevance and web search is enabled, trigger fallback
        if WEB_SEARCH_ENABLED and top_score < WEB_SEARCH_FALLBACK_THRESHOLD:
            print(f"⚠️ Low relevance ({top_score:.2f}) – triggering web search...")
            web_result = process_web_content(query)
            result = {
                "query": query,
                "response": web_result["answer"],
                "sources": web_result.get("sources", []),
                "retrieved_count": 0,
                "reranked_count": 0,
                "context": "Web search fallback used.",
                "timing": {
                    "retrieve": retrieve_time,
                    "rerank": 0,
                    "generate": 0,
                    "total": time.time() - start_time
                },
                "reranker_used": False,
                "web_fallback": True,
                "chunks_stored": web_result.get("chunks_stored", 0)
            }
            # Store in cache
            cache.set(query, result)
            return result

        # Step 3: Normal pipeline – Rerank
        rerank_start = time.time()
        reranked = self.rerank_with_bge(query, retrieved)
        rerank_time = time.time() - rerank_start
        
        # Step 4: Prepare context from top K
        top_chunks = reranked[:TOP_K_FINAL]
        
        context_parts = []
        sources = []
        for i, chunk in enumerate(top_chunks, 1):
            metadata = chunk.get('metadata', {})
            source = metadata.get('source_pdf', 'Unknown')
            page = metadata.get('page', 'N/A')
            text = metadata.get('text', '')
            page = str(page)
            
            if text:
                context_parts.append(f"[Source: {source}, Page: {page}]\n{text}")
                sources.append({"source": source, "page": page, "text": text[:200]})
            else:
                context_parts.append(f"[Source: {source}, Page: {page}]\n{chunk.get('key', 'Unknown')}")
                sources.append({"source": source, "page": page, "text": chunk.get('key', 'Unknown')})
        
        context = "\n\n---\n\n".join(context_parts)
        
        # Step 5: Generate
        gen_start = time.time()
        response = self.generate_with_groq(query, context)
        gen_time = time.time() - gen_start
        
        total_time = time.time() - start_time
        
        result = {
            "query": query,
            "response": response,
            "sources": sources,
            "retrieved_count": len(retrieved),
            "reranked_count": len(reranked),
            "context": context,
            "timing": {
                "retrieve": retrieve_time,
                "rerank": rerank_time,
                "generate": gen_time,
                "total": total_time
            },
            "reranker_used": True,
            "web_fallback": False,
            "chunks_stored": 0
        }

        # Store in cache
        cache.set(query, result)
        return result

# ============================================
# SINGLETON INSTANCE
# ============================================

try:
    rag_pipeline = RAGPipeline()
except Exception as e:
    print(f"❌ Failed to initialize RAG Pipeline: {e}")
    print("   Please ensure all dependencies are installed.")
    print("   Run: pip install transformers torch sentence-transformers")
    rag_pipeline = None