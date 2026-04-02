import os
import requests as http_requests
from typing import List, Dict, Optional

from youtube_transcript_api import YouTubeTranscriptApi
from langchain_chroma import Chroma
from langchain_core.prompts import PromptTemplate
from langchain_core.embeddings import Embeddings
from langchain_groq import ChatGroq
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv

load_dotenv()


# ── Multilingual Embeddings ────────────────────────────────────────────────────
class SentenceTransformerEmbeddings(Embeddings):
    def __init__(self, model_name: str = "paraphrase-multilingual-MiniLM-L12-v2"):
        self.model = SentenceTransformer(model_name)

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return self.model.encode(texts).tolist()

    def embed_query(self, text: str) -> List[float]:
        return self.model.encode([text])[0].tolist()


# ── Timestamp Utilities ────────────────────────────────────────────────────────
def format_timestamp(seconds: float) -> str:
    """Convert seconds to MM:SS or HH:MM:SS string."""
    s = int(seconds)
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{sec:02d}" if h > 0 else f"{m:02d}:{sec:02d}"


def create_timed_chunks(snippets, target_chars: int = 900, overlap_chars: int = 150):
    """
    Split transcript into chunks while preserving the START TIMESTAMP
    of the first snippet in each chunk — enables timestamp-grounded answers.
    """
    if not snippets:
        return []

    chunks = []
    current_text = ""
    current_start = snippets[0].start

    for snippet in snippets:
        if len(current_text) + len(snippet.text) > target_chars and current_text:
            chunks.append({"text": current_text.strip(), "start": current_start})
            # Overlap: keep last N chars for context continuity
            current_text = current_text[-overlap_chars:] + " " + snippet.text
            current_start = snippet.start
        else:
            if not current_text:
                current_start = snippet.start
            current_text += " " + snippet.text

    if current_text.strip():
        chunks.append({"text": current_text.strip(), "start": current_start})

    return chunks


# ── RAG Service ────────────────────────────────────────────────────────────────
class RAGService:
    COLLECTION_NAME = "youtube_rag_kb"

    def __init__(self):
        self.embeddings = SentenceTransformerEmbeddings("paraphrase-multilingual-MiniLM-L12-v2")
        self.persist_directory = "./chroma_db"
        self._vectorstore: Optional[Chroma] = None

        # In-memory video registry: { video_id -> {title, url} }
        self.video_registry: Dict[str, dict] = {}

        api_key = os.getenv("GROQ_API_KEY")
        self.llm = None
        if api_key and api_key != "your_groq_api_key_here":
            self.llm = ChatGroq(model_name="llama-3.3-70b-versatile", api_key=api_key)

    @property
    def vectorstore(self) -> Chroma:
        """Lazily initialise shared ChromaDB collection."""
        if self._vectorstore is None:
            self._vectorstore = Chroma(
                collection_name=self.COLLECTION_NAME,
                embedding_function=self.embeddings,
                persist_directory=self.persist_directory,
            )
        return self._vectorstore

    def check_llm_ready(self):
        if not self.llm:
            api_key = os.getenv("GROQ_API_KEY")
            if api_key and api_key != "your_groq_api_key_here":
                self.llm = ChatGroq(model_name="llama-3.3-70b-versatile", api_key=api_key)
            else:
                raise ValueError("Groq API key not set in .env file.")

    # ── Helpers ──────────────────────────────────────────────────────────────
    def extract_video_id(self, url: str) -> str:
        if "v=" in url:
            return url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            return url.split("youtu.be/")[1].split("?")[0]
        elif "shorts/" in url:
            return url.split("shorts/")[1].split("?")[0]
        return url.strip()

    def get_video_title(self, video_id: str) -> str:
        """Fetch video title via YouTube oEmbed (no API key required)."""
        try:
            resp = http_requests.get(
                f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={video_id}&format=json",
                timeout=6
            )
            if resp.ok:
                return resp.json().get("title", video_id)
        except Exception:
            pass
        return video_id

    def is_video_indexed(self, video_id: str) -> bool:
        try:
            results = self.vectorstore.get(where={"video_id": video_id}, limit=1)
            return len(results["ids"]) > 0
        except Exception:
            return False

    # ── Core: Process Video ───────────────────────────────────────────────────
    def process_video(self, url: str) -> dict:
        """Extract transcript, create timestamp-aware chunks, store in shared KB."""
        video_id = self.extract_video_id(url)
        canonical_url = f"https://www.youtube.com/watch?v={video_id}"

        # Already in registry = already done
        if video_id in self.video_registry:
            info = self.video_registry[video_id]
            return {
                "video_id": video_id,
                "video_title": info["title"],
                "video_url": canonical_url,
                "message": "Already in knowledge base."
            }

        # Also check persistent Chroma (survives server restarts)
        if self.is_video_indexed(video_id):
            title = self.get_video_title(video_id)
            self.video_registry[video_id] = {"title": title, "url": canonical_url}
            return {
                "video_id": video_id,
                "video_title": title,
                "video_url": canonical_url,
                "message": "Already in knowledge base."
            }

        try:
            # 1. Title
            title = self.get_video_title(video_id)

            # 2. Transcript (any language)
            ytt_api = YouTubeTranscriptApi()
            transcript_list = ytt_api.list(video_id)

            fetched = None
            try:
                for t in transcript_list:
                    if not t.is_generated:
                        fetched = t.fetch()
                        break
            except Exception:
                pass
            if fetched is None:
                fetched = ytt_api.fetch(video_id)

            # 3. Timestamp-aware chunking
            timed_chunks = create_timed_chunks(list(fetched), target_chars=900, overlap_chars=150)

            # 4. Store in shared Chroma collection with full metadata
            texts = [c["text"] for c in timed_chunks]
            metadatas = [
                {
                    "video_id":          video_id,
                    "video_title":       title,
                    "video_url":         canonical_url,
                    "start_seconds":     c["start"],
                    "timestamp_display": format_timestamp(c["start"]),
                    "timestamp_url":     f"{canonical_url}&t={int(c['start'])}s",
                }
                for c in timed_chunks
            ]
            self.vectorstore.add_texts(texts=texts, metadatas=metadatas)

            # 5. Register
            self.video_registry[video_id] = {"title": title, "url": canonical_url}

            return {
                "video_id":    video_id,
                "video_title": title,
                "video_url":   canonical_url,
                "message":     f"Indexed {len(timed_chunks)} timestamp-aware chunks."
            }

        except Exception as e:
            raise Exception(f"Failed to process video: {str(e)}")

    # ── Core: List Videos ─────────────────────────────────────────────────────
    def get_all_videos(self) -> List[dict]:
        return [
            {"video_id": vid, "video_title": info["title"], "video_url": info["url"]}
            for vid, info in self.video_registry.items()
        ]

    # ── Core: Ask Question ────────────────────────────────────────────────────
    def ask_question(self, question: str, video_ids: Optional[List[str]] = None) -> dict:
        """
        Search across all indexed videos (or filter to specific ones).
        Returns answer + timestamp-grounded source citations.
        """
        self.check_llm_ready()

        # Build optional Chroma filter
        where_filter = None
        if video_ids:
            where_filter = (
                {"video_id": video_ids[0]} if len(video_ids) == 1
                else {"video_id": {"$in": video_ids}}
            )

        # Retrieve top-k relevant chunks with similarity scores
        docs_and_scores = self.vectorstore.similarity_search_with_score(
            question, k=5, filter=where_filter
        )

        if not docs_and_scores:
            return {
                "answer": "No relevant content found. Please add at least one video to the knowledge base first.",
                "sources": []
            }

        context = "\n\n---\n\n".join([doc.page_content for doc, _ in docs_and_scores])

        # Build deduplicated source citations
        seen = set()
        sources = []
        for doc, score in docs_and_scores:
            m = doc.metadata
            key = (m.get("video_id"), m.get("timestamp_display"))
            if key not in seen:
                seen.add(key)
                sources.append({
                    "video_title":   m.get("video_title", "Unknown Video"),
                    "video_url":     m.get("video_url", ""),
                    "timestamp":     m.get("timestamp_display", "00:00"),
                    "timestamp_url": m.get("timestamp_url", m.get("video_url", "")),
                })

        # LLM answer
        prompt_template = """
You are a helpful AI that answers questions using ONLY the provided YouTube transcript excerpts.
RULES:
- Use ONLY the context below. Never use external knowledge.
- If the context doesn't contain the answer, say "The video doesn't cover this topic."
- Detect and match the question's language in your answer.
- Be concise and specific.

Context from video transcripts:
{context}

Question: {question}

Answer (in the same language as the question):
"""
        prompt = PromptTemplate(template=prompt_template, input_variables=["context", "question"])
        response = (prompt | self.llm).invoke({"context": context, "question": question})

        return {"answer": response.content, "sources": sources}

    # ── Core: Notes Generator ─────────────────────────────────────────────────
    def _get_video_chunks(self, video_ids=None, limit=60):
        """Retrieve transcript chunks sorted by timestamp (for notes / key moments)."""
        where_filter = None
        if video_ids:
            where_filter = (
                {"video_id": video_ids[0]} if len(video_ids) == 1
                else {"video_id": {"$in": video_ids}}
            )

        results = self.vectorstore.get(
            where=where_filter,
            limit=limit,
            include=["documents", "metadatas"]
        )

        if not results["documents"]:
            return []

        pairs = sorted(
            zip(results["documents"], results["metadatas"]),
            key=lambda x: x[1].get("start_seconds", 0)
        )
        return pairs

    def generate_notes(self, video_ids: Optional[List[str]] = None) -> str:
        """Generate structured study notes from indexed video(s)."""
        self.check_llm_ready()

        chunks = self._get_video_chunks(video_ids, limit=60)
        if not chunks:
            raise ValueError("No content found. Please index a video first.")

        # Sample evenly for token efficiency (~15 chunks)
        step = max(1, len(chunks) // 15)
        sampled = chunks[::step][:15]
        transcript_sample = "\n\n".join(
            f"[{meta.get('timestamp_display', '?')}] {text}"
            for text, meta in sampled
        )

        prompt = f"""You are an expert study-note writer. Convert this YouTube transcript into clean, structured study notes.

Use this exact format:
## 📌 Main Topics
1. Topic — brief explanation
2. ...

## 🔑 Key Concepts
- **Concept**: clear definition

## 💡 Important Points
- Point 1
- Point 2

## 📝 Summary
2–3 sentence summary of the whole video.

Transcript (with timestamps for reference):
{transcript_sample}

Generate structured study notes:"""

        response = self.llm.invoke(prompt)
        return response.content

    # ── Core: Key Moments ─────────────────────────────────────────────────────
    def get_key_moments(self, video_id: str) -> List[dict]:
        """Identify the most important moments in a single video with timestamps."""
        import json, re

        self.check_llm_ready()

        chunks = self._get_video_chunks([video_id], limit=80)
        if not chunks:
            raise ValueError("Video not indexed. Please add it to the knowledge base first.")

        # Sample evenly, keeping timestamps visible to LLM (~15 moments)
        step = max(1, len(chunks) // 15)
        sampled = chunks[::step][:15]
        ts_transcript = "\n\n".join(
            f"[{meta.get('timestamp_display','?')}] {text}"
            for text, meta in sampled
        )

        prompt = f"""Analyze this YouTube video transcript and identify the 6–8 most important key moments.

For each key moment output:
- The timestamp exactly as shown in brackets like [MM:SS]
- A short title (4–7 words)
- A 1-sentence description of what happens

Respond ONLY with a valid JSON array — no markdown, no extra text:
[
  {{"timestamp": "MM:SS", "title": "...", "description": "..."}},
  ...
]

Transcript:
{ts_transcript}

JSON:"""

        response = self.llm.invoke(prompt)
        text = response.content.strip()

        # Extract JSON array robustly
        match = re.search(r'\[.*?\]', text, re.DOTALL)
        if not match:
            raise ValueError("Could not parse key moments from AI response.")

        moments = json.loads(match.group())

        # Attach clickable YouTube deeplinks
        video_url = f"https://www.youtube.com/watch?v={video_id}"
        for m in moments:
            ts = m.get("timestamp", "00:00")
            parts = ts.split(":")
            try:
                if len(parts) == 3:
                    secs = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                else:
                    secs = int(parts[0]) * 60 + int(parts[1])
            except ValueError:
                secs = 0
            m["timestamp_url"] = f"{video_url}&t={secs}s"

        return moments


rag_service = RAGService()
