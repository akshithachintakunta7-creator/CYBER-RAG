"""
Semantic Chunking using Embedding Similarity
Detects natural breakpoints where sentences/paragraphs diverge in meaning.
Includes checkpoint: skips already chunked files.
"""

import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass, field, asdict
import logging
from tqdm import tqdm
import re
import hashlib

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Try to import sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
    EMBEDDINGS_AVAILABLE = True
except ImportError:
    EMBEDDINGS_AVAILABLE = False
    logger.error("sentence-transformers required. Run: pip install sentence-transformers")
    exit(1)

# For token counting
try:
    import tiktoken
    TOKENIZER = tiktoken.get_encoding("cl100k_base")
    TOKENIZER_AVAILABLE = True
except ImportError:
    TOKENIZER_AVAILABLE = False
    TOKENIZER = None


@dataclass
class Chunk:
    chunk_id: str
    document_id: str
    source_pdf: str
    pages: List[int]
    section: Optional[str]
    citations: List[str]
    ocr_confidence: float
    text: str
    chunk_type: str = "semantic"
    has_figure_references: List[str] = field(default_factory=list)
    is_reference_section: bool = False
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def get_token_count(self) -> int:
        if TOKENIZER_AVAILABLE:
            return len(TOKENIZER.encode(self.text))
        return len(self.text) // 4


class EmbeddingSemanticChunker:
    """Chunk documents using embedding similarity to detect semantic boundaries."""
    
    def __init__(
        self,
        embedding_model: str = "all-MiniLM-L6-v2",
        similarity_threshold: float = 0.65,   # Drop below this -> break chunk
        min_chunk_tokens: int = 200,
        max_chunk_tokens: int = 800,
        overlap_tokens: int = 80,
        window_size: int = 3                   # Sentences per embedding window
    ):
        self.model = SentenceTransformer(embedding_model)
        self.similarity_threshold = similarity_threshold
        self.min_chunk_tokens = min_chunk_tokens
        self.max_chunk_tokens = max_chunk_tokens
        self.overlap_tokens = overlap_tokens
        self.window_size = window_size
        
        # Patterns for metadata extraction
        self.cve_pattern = re.compile(r'CVE-\d{4}-\d{4,7}', re.IGNORECASE)
        self.cwe_pattern = re.compile(r'CWE-\d+', re.IGNORECASE)
        self.rfc_pattern = re.compile(r'RFC\s*\d+', re.IGNORECASE)
        
    def chunk_document(self, json_path: Path) -> List[Chunk]:
        """Chunk a single preprocessed JSON document."""
        with open(json_path, 'r', encoding='utf-8') as f:
            doc = json.load(f)
        
        doc_id = f"DOC_{hashlib.md5(str(json_path).encode()).hexdigest()[:12]}"
        source_pdf = doc.get('file_name', json_path.stem)
        
        # Extract page texts
        pages = doc.get('pages', [])
        if not pages:
            return []
        
        page_texts = {}
        page_confidences = {}
        for page in pages:
            num = page.get('page')
            text = page.get('text', '')
            if text.strip():
                page_texts[num] = text
                page_confidences[num] = page.get('confidence', 1.0)
        
        if not page_texts:
            return []
        
        # Build a list of sentences with their page numbers
        sentences = self._extract_sentences_with_pages(page_texts)
        if len(sentences) < 2:
            # Fallback to paragraph splitting
            return self._paragraph_fallback(doc, doc_id, source_pdf, page_texts, page_confidences)
        
        # Compute embeddings for each sentence
        sent_texts = [s['text'] for s in sentences]
        embeddings = self.model.encode(sent_texts, normalize_embeddings=True)
        
        # Compute similarity between consecutive windows of sentences
        breakpoints = self._find_semantic_breakpoints(embeddings)
        
        # Build chunks from sentences using breakpoints
        chunks = self._build_chunks_from_breakpoints(
            sentences, breakpoints, doc_id, source_pdf, doc, page_confidences
        )
        
        return chunks
    
    def chunk_text(self, text: str, source: str = "web") -> List[Chunk]:
        """
        Chunk raw text (from web search or uploaded files) into semantic chunks.
        Returns a list of Chunk objects with source metadata.
        """
        if not text or not text.strip():
            return []
        
        # Split text into sentences (same as page extraction but without page numbers)
        sentences = []
        raw_sents = re.split(r'(?<=[.!?])\s+', text)
        for sent in raw_sents:
            sent = sent.strip()
            if len(sent) > 10:  # ignore very short fragments
                sentences.append({'text': sent, 'page': 1})  # assign dummy page 1
        
        if len(sentences) < 2:
            # If only one sentence, treat entire text as one chunk
            chunk = self._create_chunk(
                [{'text': text, 'page': 1}],
                doc_id=source,
                source_pdf=source,
                doc={},
                page_confidences={}
            )
            return [chunk] if chunk else []
        
        # Compute embeddings for sentences
        sent_texts = [s['text'] for s in sentences]
        embeddings = self.model.encode(sent_texts, normalize_embeddings=True)
        
        # Find semantic breakpoints
        breakpoints = self._find_semantic_breakpoints(embeddings)
        
        # Build chunks using the existing method with dummy values
        chunks = self._build_chunks_from_breakpoints(
            sentences,
            breakpoints,
            doc_id=source,
            source_pdf=source,
            doc={},
            page_confidences={}
        )
        
        return chunks
    
    def _extract_sentences_with_pages(self, page_texts: Dict[int, str]) -> List[Dict]:
        """Split text into sentences, keeping page numbers."""
        sentences = []
        for page_num, text in sorted(page_texts.items()):
            # Simple sentence splitting (can be improved)
            raw_sents = re.split(r'(?<=[.!?])\s+', text)
            for sent in raw_sents:
                sent = sent.strip()
                if len(sent) > 10:  # ignore very short fragments
                    sentences.append({'text': sent, 'page': page_num})
        return sentences
    
    def _find_semantic_breakpoints(self, embeddings: np.ndarray) -> List[int]:
        """
        Find indices where semantic similarity drops below threshold.
        Uses a sliding window to compare mean embedding of preceding vs succeeding sentences.
        """
        breakpoints = []
        n = len(embeddings)
        if n < 2:
            return []
        
        for i in range(self.window_size, n - self.window_size):
            # Compute mean embedding of left window and right window
            left_emb = embeddings[i - self.window_size:i].mean(axis=0)
            right_emb = embeddings[i:i + self.window_size].mean(axis=0)
            # Cosine similarity (vectors are normalized)
            sim = np.dot(left_emb, right_emb)
            if sim < self.similarity_threshold:
                breakpoints.append(i)
        
        # Also add breakpoints when token count exceeds max (will be handled later)
        return breakpoints
    
    def _build_chunks_from_breakpoints(
        self, sentences, breakpoints, doc_id, source_pdf, doc, page_confidences
    ) -> List[Chunk]:
        """Group sentences into chunks using breakpoints, respecting token limits."""
        chunks = []
        start_idx = 0
        for bp in breakpoints:
            # Create chunk from start_idx to bp-1
            chunk_sents = sentences[start_idx:bp]
            if chunk_sents:
                chunk = self._create_chunk(chunk_sents, doc_id, source_pdf, doc, page_confidences)
                if chunk and chunk.get_token_count() >= self.min_chunk_tokens:
                    chunks.append(chunk)
                elif chunk and chunk.get_token_count() < self.min_chunk_tokens:
                    # Merge with next chunk later, but for now append and merge later
                    chunks.append(chunk)
            start_idx = bp
        
        # Last chunk
        if start_idx < len(sentences):
            chunk_sents = sentences[start_idx:]
            chunk = self._create_chunk(chunk_sents, doc_id, source_pdf, doc, page_confidences)
            if chunk:
                chunks.append(chunk)
        
        # Merge chunks that are too small with adjacent chunks
        chunks = self._merge_small_chunks(chunks)
        
        # Ensure chunks respect max token limit (split if necessary)
        chunks = self._enforce_max_tokens(chunks)
        
        return chunks
    
    def _create_chunk(self, sentences: List[Dict], doc_id: str, source_pdf: str, doc: Dict, page_confidences: Dict) -> Optional[Chunk]:
        if not sentences:
            return None
        
        text = ' '.join([s['text'] for s in sentences])
        pages = list(set([s['page'] for s in sentences]))
        # token_count is not used later, so we can remove or keep
        # token_count = len(TOKENIZER.encode(text)) if TOKENIZER_AVAILABLE else len(text)//4
        
        # Extract citations
        citations = set()
        citations.update(self.cve_pattern.findall(text))
        citations.update(self.cwe_pattern.findall(text))
        citations.update(self.rfc_pattern.findall(text))
        
        # OCR confidence
        confs = [page_confidences.get(p, 1.0) for p in pages]
        ocr_conf = sum(confs)/len(confs) if confs else 1.0
        
        chunk_id = f"{doc_id}_p{min(pages)}_{hashlib.md5(text[:100].encode()).hexdigest()[:6]}"
        
        # Determine if it's a reference section
        is_ref = bool(re.search(r'\b(?:references|bibliography|works cited)\b', text[:200], re.IGNORECASE))
        
        # Extract section heading (simple heuristic: first line that is short and ends with colon or is uppercase)
        section = None
        lines = text.split('\n')
        for line in lines[:3]:
            if len(line) < 80 and (line.endswith(':') or line.isupper() or re.match(r'^\d+\.', line)):
                section = line.strip()
                break
        
        return Chunk(
            chunk_id=chunk_id,
            document_id=doc_id,
            source_pdf=source_pdf,
            pages=pages,
            section=section,
            citations=list(citations),
            ocr_confidence=ocr_conf,
            text=text,
            chunk_type="semantic",
            is_reference_section=is_ref
        )
    
    def _merge_small_chunks(self, chunks: List[Chunk]) -> List[Chunk]:
        """Merge consecutive small chunks to reach min_chunk_tokens."""
        if len(chunks) < 2:
            return chunks
        
        merged = []
        i = 0
        while i < len(chunks):
            current = chunks[i]
            if current.get_token_count() < self.min_chunk_tokens and i+1 < len(chunks):
                # Merge with next
                next_chunk = chunks[i+1]
                combined_text = current.text + " " + next_chunk.text
                combined_pages = sorted(set(current.pages + next_chunk.pages))
                combined_citations = list(set(current.citations + next_chunk.citations))
                combined_figures = list(set(current.has_figure_references + next_chunk.has_figure_references))
                ocr_conf = min(current.ocr_confidence, next_chunk.ocr_confidence)
                new_chunk = Chunk(
                    chunk_id=current.chunk_id,  # keep first ID
                    document_id=current.document_id,
                    source_pdf=current.source_pdf,
                    pages=combined_pages,
                    section=current.section or next_chunk.section,
                    citations=combined_citations,
                    ocr_confidence=ocr_conf,
                    text=combined_text,
                    chunk_type="merged",
                    has_figure_references=combined_figures,
                    is_reference_section=current.is_reference_section or next_chunk.is_reference_section
                )
                merged.append(new_chunk)
                i += 2
            else:
                merged.append(current)
                i += 1
        return merged
    
    def _enforce_max_tokens(self, chunks: List[Chunk]) -> List[Chunk]:
        """Split chunks that exceed max_chunk_tokens."""
        final_chunks = []
        for chunk in chunks:
            if chunk.get_token_count() <= self.max_chunk_tokens:
                final_chunks.append(chunk)
            else:
                # Split by sentences again
                sentences = re.split(r'(?<=[.!?])\s+', chunk.text)
                if len(sentences) <= 1:
                    final_chunks.append(chunk)
                    continue
                # Group sentences into smaller chunks
                sub_chunks = []
                current = []
                current_tokens = 0
                for sent in sentences:
                    sent_tokens = len(TOKENIZER.encode(sent)) if TOKENIZER_AVAILABLE else len(sent)//4
                    if current_tokens + sent_tokens > self.max_chunk_tokens and current:
                        sub_text = ' '.join(current)
                        sub_chunk = Chunk(
                            chunk_id=f"{chunk.chunk_id}_sub{len(sub_chunks)}",
                            document_id=chunk.document_id,
                            source_pdf=chunk.source_pdf,
                            pages=chunk.pages,
                            section=chunk.section,
                            citations=chunk.citations,
                            ocr_confidence=chunk.ocr_confidence,
                            text=sub_text,
                            chunk_type="split",
                            is_reference_section=chunk.is_reference_section
                        )
                        sub_chunks.append(sub_chunk)
                        current = []
                        current_tokens = 0
                    current.append(sent)
                    current_tokens += sent_tokens
                if current:
                    sub_text = ' '.join(current)
                    sub_chunk = Chunk(
                        chunk_id=f"{chunk.chunk_id}_sub{len(sub_chunks)}",
                        document_id=chunk.document_id,
                        source_pdf=chunk.source_pdf,
                        pages=chunk.pages,
                        section=chunk.section,
                        citations=chunk.citations,
                        ocr_confidence=chunk.ocr_confidence,
                        text=sub_text,
                        chunk_type="split",
                        is_reference_section=chunk.is_reference_section
                    )
                    sub_chunks.append(sub_chunk)
                final_chunks.extend(sub_chunks)
        return final_chunks
    
    def _paragraph_fallback(self, doc, doc_id, source_pdf, page_texts, page_confidences):
        """Fallback chunking using paragraph breaks if sentence splitting fails."""
        # Use previous paragraph-based chunker logic (simplified)
        all_text = []
        for page_num, text in sorted(page_texts.items()):
            all_text.append(f"[PAGE {page_num}]\n{text}")
        full_text = '\n\n'.join(all_text)
        paragraphs = re.split(r'\n\s*\n', full_text)
        chunks = []
        current_chunk = []
        current_tokens = 0
        for para in paragraphs:
            para = re.sub(r'\[PAGE \d+\]\n?', '', para).strip()
            if not para:
                continue
            tokens = len(TOKENIZER.encode(para)) if TOKENIZER_AVAILABLE else len(para)//4
            if current_tokens + tokens > self.max_chunk_tokens and current_chunk:
                text = '\n\n'.join(current_chunk)
                chunk = self._create_chunk([{'text': text, 'page': 1}], doc_id, source_pdf, doc, page_confidences)
                if chunk:
                    chunks.append(chunk)
                current_chunk = [para]
                current_tokens = tokens
            else:
                current_chunk.append(para)
                current_tokens += tokens
        if current_chunk:
            text = '\n\n'.join(current_chunk)
            chunk = self._create_chunk([{'text': text, 'page': 1}], doc_id, source_pdf, doc, page_confidences)
            if chunk:
                chunks.append(chunk)
        return chunks


def process_all_documents(input_dir: str, output_dir: str, chunker: EmbeddingSemanticChunker):
    """Process all JSON files in input_dir and save chunks, skipping already processed files."""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    json_files = list(input_path.glob("*.json"))
    logger.info(f"Found {len(json_files)} documents to chunk")
    
    # Determine which files are already chunked
    existing_chunks = set()
    for out_file in output_path.glob("*_chunks.json"):
        # Extract original stem: remove "_chunks" suffix
        original_stem = out_file.stem.replace("_chunks", "")
        existing_chunks.add(original_stem)
    
    files_to_process = [f for f in json_files if f.stem not in existing_chunks]
    logger.info(f"Skipping {len(existing_chunks)} already processed files. {len(files_to_process)} files remaining.")
    
    if not files_to_process:
        logger.info("All files already chunked. Nothing to do.")
        return
    
    total_chunks = 0
    for json_file in tqdm(files_to_process, desc="Chunking documents"):
        try:
            chunks = chunker.chunk_document(json_file)
            if chunks:
                out_file = output_path / f"{json_file.stem}_chunks.json"
                with open(out_file, 'w', encoding='utf-8') as f:
                    json.dump([c.to_dict() for c in chunks], f, indent=2)
                total_chunks += len(chunks)
                logger.debug(f"  {json_file.name} -> {len(chunks)} chunks")
        except Exception as e:
            logger.error(f"Failed on {json_file.name}: {e}")
    
    logger.info(f"Done. Total new chunks created: {total_chunks}")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", "-i", default="output_json", help="Directory with preprocessed JSON")
    parser.add_argument("--output", "-o", default="chunks", help="Output directory for chunks")
    parser.add_argument("--threshold", "-t", type=float, default=0.65, help="Similarity threshold (lower = more chunks)")
    parser.add_argument("--min-tokens", type=int, default=200, help="Minimum chunk tokens")
    parser.add_argument("--max-tokens", type=int, default=800, help="Maximum chunk tokens")
    args = parser.parse_args()
    
    chunker = EmbeddingSemanticChunker(
        similarity_threshold=args.threshold,
        min_chunk_tokens=args.min_tokens,
        max_chunk_tokens=args.max_tokens
    )
    process_all_documents(args.input, args.output, chunker)