"""
Web Search module for RAG fallback
Fetches content from the web, chunks, embeds, stores, then generates answer.
"""

import os
import re
import hashlib
from typing import List, Dict, Any
import requests
from bs4 import BeautifulSoup
from tavily import TavilyClient

from backend.config import TAVILY_API_KEY, VECTOR_BUCKET_NAME, INDEX_NAME
from backend.semantic_chunking_embedding import EmbeddingSemanticChunker, Chunk

# Initialize Tavily client
tavily = TavilyClient(api_key=TAVILY_API_KEY)

def search_web(query: str, max_results: int = 5) -> List[Dict]:
    """Search the web using Tavily API."""
    try:
        response = tavily.search(
            query=query,
            search_depth="advanced",
            max_results=max_results,
            include_answer=True,
            include_raw_content=True
        )
        
        results = []
        if response.get("answer"):
            results.append({
                "title": "Answer Summary",
                "url": None,
                "content": response["answer"],
                "source": "tavily_summary"
            })
        
        for result in response.get("results", []):
            results.append({
                "title": result.get("title", ""),
                "url": result.get("url", ""),
                "content": result.get("content", ""),
                "raw_content": result.get("raw_content", ""),
                "source": "tavily"
            })
        
        return results
    except Exception as e:
        print(f"❌ Web search error: {e}")
        return []

def extract_full_text(url: str) -> str:
    """Extract full text from a webpage using requests + BeautifulSoup."""
    try:
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        for tag in soup(['script', 'style', 'nav', 'footer', 'header']):
            tag.decompose()
        
        text = soup.get_text(separator='\n', strip=True)
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r' +', ' ', text)
        
        return text[:8000]
    except Exception as e:
        print(f"❌ Error extracting text from {url}: {e}")
        return ""

def process_web_content(query: str, max_results: int = 3) -> Dict[str, Any]:
    """
    Main function: Search web → extract → chunk → embed → store → generate answer.
    print(f"🔍 process_web_content called for: {query}")"""
    print(f"🔍 Searching web for: {query}")
    search_results = search_web(query, max_results)
    
    if not search_results:
        return {
            "answer": "I couldn't find any relevant information on the web.",
            "chunks_stored": 0,
            "sources": [],
            "chunk_ids": []
        }
    
    # 2. Extract full content
    all_text = []
    sources = []
    
    for result in search_results:
        if result.get("source") == "tavily_summary":
            all_text.append(result["content"])
            sources.append({"title": "Answer Summary", "url": None})
            continue
        
        if result.get("url"):
            full_text = extract_full_text(result["url"])
            if full_text and len(full_text) > 100:
                all_text.append(full_text)
                sources.append({
                    "title": result.get("title", "Web Page"),
                    "url": result.get("url")
                })
            elif result.get("content"):
                all_text.append(result["content"])
                sources.append({
                    "title": result.get("title", "Web Page"),
                    "url": result.get("url")
                })
    
    combined_text = "\n\n".join(all_text)
    print(f"📝 Extracted {len(combined_text)} characters of text")
    
    if len(combined_text) < 100:
        return {
            "answer": "I found some results but couldn't extract enough readable content.",
            "chunks_stored": 0,
            "sources": sources,
            "chunk_ids": []
        }
    
    # 3. Semantic chunking
    print("📦 Chunking web content...")
    chunker = EmbeddingSemanticChunker(
        embedding_model="all-MiniLM-L6-v2",
        similarity_threshold=0.65,
        min_chunk_tokens=200,
        max_chunk_tokens=800,
        overlap_tokens=80
    )
    
    chunks = chunker.chunk_text(combined_text, source="web_search")
    
    if not chunks:
        return {
            "answer": "Could not chunk the web content.",
            "chunks_stored": 0,
            "sources": sources,
            "chunk_ids": []
        }
    
    # 4. Store in S3 Vectors
    print(f"📤 Storing {len(chunks)} chunks in vector DB...")
    from backend.rag_pipeline import rag_pipeline
    
    stored_ids = []
    for idx, chunk in enumerate(chunks):
        try:
            embedding = rag_pipeline.embedding_model.encode(
                chunk.text, 
                normalize_embeddings=True
            )
            
            vector_key = f"web_{hashlib.md5(chunk.text.encode()).hexdigest()[:12]}"
            
            rag_pipeline.s3vectors.put_vectors(
                vectorBucketName=VECTOR_BUCKET_NAME,
                indexName=INDEX_NAME,
                vectors=[{
                    "key": vector_key,
                    "data": {"float32": embedding.tolist()},
                    "metadata": {
                        "source_pdf": "web_search",
                        "chunk_id": chunk.chunk_id,
                        "text": chunk.text[:300],
                        "web_query": query[:100]
                    }
                }]
            )
            stored_ids.append(vector_key)
        except Exception as e:
            print(f"❌ Error storing chunk {idx}: {e}")
    
    print(f"✅ Stored {len(stored_ids)} chunks in vector DB")
    
    # 5. Generate answer using Groq with the web content
    print("🤖 Generating response...")
    from groq import Groq
    from backend.config import GROQ_API_KEY, GROQ_MODEL
    
    client = Groq(api_key=GROQ_API_KEY)
    context = combined_text[:8000]
    
    prompt = f"""Based on the following web search results, answer the user's question.

Web Content:
{context}

Question: {query}

Provide a clear, accurate answer based ONLY on the information above. If the information is insufficient, say so.

Answer:"""
    
    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=1024
        )
        answer = response.choices[0].message.content
    except Exception as e:
        answer = f"Error generating response: {e}"
    
    return {
        "answer": answer,
        "chunks_stored": len(stored_ids),
        "sources": sources[:5],
        "chunk_ids": stored_ids,
        "query": query,
        "web_fallback": True
    }