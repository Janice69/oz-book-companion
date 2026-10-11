"""Serve the local chatbot and its browser interface."""
import logging
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from rag import ANSWER_MODEL, BookRAG

ROOT = Path(__file__).parent
app = FastAPI(title="Oz Book Companion")
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
engine = None
status = "loading"
generation_lock = threading.Lock()


def load_engine():
    global engine, status
    try:
        engine = BookRAG()
        status = "ready"
    except Exception:
        logging.exception("Could not load RAG models")
        status = "error"


@app.on_event("startup")
def startup():
    threading.Thread(target=load_engine, daemon=True).start()


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


@app.get("/")
def homepage():
    return FileResponse(ROOT / "static" / "index.html")


@app.get("/how-rag")
def rag_explainer():
    return FileResponse(ROOT / "static" / "how-rag.html")


@app.get("/api/status")
def model_status():
    return {"status": status, "passages": len(engine.passages) if engine else 0, "model": ANSWER_MODEL}


@app.post("/api/chat")
def chat(body: ChatRequest):
    question = body.question.strip()
    if not question:
        raise HTTPException(400, "Please enter a question.")
    if status != "ready":
        raise HTTPException(503, "Models are still loading, or setup failed. Check the server terminal.")
    if not generation_lock.acquire(blocking=False):
        raise HTTPException(429, "An answer is already being generated. Try again shortly.")
    try:
        return engine.answer(question)
    except Exception:
        logging.exception("Answer generation failed")
        raise HTTPException(500, "The answer could not be generated. Please try again.")
    finally:
        generation_lock.release()
