from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import os
import uvicorn

from rag_service import rag_service

app = FastAPI(title="YouTube RAG API — Multi-Video with Timestamps")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    return {"status": "ok", "message": "YouTube RAG API is running"}


class ProcessRequest(BaseModel):
    url: str

class ChatRequest(BaseModel):
    question: str
    video_ids: Optional[List[str]] = None  # None / [] = search ALL indexed videos

class NotesRequest(BaseModel):
    video_ids: Optional[List[str]] = None

class KeyMomentsRequest(BaseModel):
    video_id: str


@app.post("/api/process-video")
async def process_video(request: ProcessRequest):
    try:
        return rag_service.process_video(request.url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/videos")
async def get_all_videos():
    return rag_service.get_all_videos()


@app.post("/api/chat")
async def chat(request: ChatRequest):
    try:
        return rag_service.ask_question(request.question, request.video_ids)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/generate-notes")
async def generate_notes(request: NotesRequest):
    try:
        notes = rag_service.generate_notes(request.video_ids)
        return {"notes": notes}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/key-moments")
async def key_moments(request: KeyMomentsRequest):
    try:
        moments = rag_service.get_key_moments(request.video_id)
        return {"moments": moments}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
