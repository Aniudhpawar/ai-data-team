"""The website's backend. Run from the project root:

    uvicorn src.api.main:app --reload

then open http://localhost:8000
"""
import json
import logging
import os
import queue
import threading
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.agents import config
from src.agents.charts import best_chart
from src.agents.team import run_team
from src.api import dashboard as dash
from src.api.limits import AnswerCache, DailyCap, RateLimiter

log = logging.getLogger("ai-data-team")
ROOT = Path(__file__).resolve().parents[2]

MAX_CHARS = int(os.getenv("MAX_QUESTION_CHARS", "300"))
limiter = RateLimiter(int(os.getenv("ASK_PER_MINUTE", "5")))
daily = DailyCap(int(os.getenv("ASK_PER_DAY", "200")))
cache = AnswerCache()

SUGGESTED = [
    "How did revenue change from 2024 to 2025, and which category drove the change?",
    "Which month had the deepest month-over-month drop in sales in each year from 2020 to 2026?",
    "What are the top 5 products by revenue?",
    "Which acquisition channel brings in the most revenue?",
    "How does revenue in the last 12 months compare with the 12 months before?",
]

app = FastAPI(title="AI Data Team", docs_url="/api/docs", openapi_url="/api/openapi.json")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.getenv(
        "CORS_ORIGINS", "http://localhost:8000,http://127.0.0.1:8000,http://localhost:5500,http://127.0.0.1:5500"
    ).split(",") if o],
    allow_methods=["GET", "POST"], allow_headers=["*"])


class Ask(BaseModel):
    question: str


def _source(request):
    if os.getenv("TRUST_PROXY") == "1":
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            return fwd.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _friendly(e):
    log.exception("ask failed")
    text = str(e).lower()
    if "token" in text or "auth" in text or "401" in text or "403" in text:
        return "The model service rejected the credentials. Check the keys in your .env file."
    if "csv" in text or "no such file" in text:
        return "The data files were not found. Check that data/raw contains the four CSV files."
    return "The team could not finish this question. Try rephrasing it or ask again."


@app.get("/api/health")
def health():
    info = {"status": "ok", "data_backend": config.DATA_BACKEND, "llm_backend": config.LLM_BACKEND,
            "model": {"databricks": config.MODEL, "anthropic": config.ANTHROPIC_MODEL,
                      "mock": "scripted mock"}.get(config.LLM_BACKEND, config.LLM_BACKEND),
            "questions_left_today": daily.remaining(), "suggested": SUGGESTED}
    return info


@app.get("/api/dashboard")
def get_dashboard():
    try:
        return dash.dashboard()
    except Exception as e:
        raise HTTPException(503, _friendly(e))


@app.get("/api/quality")
def get_quality():
    try:
        return dash.quality()
    except Exception as e:
        raise HTTPException(503, _friendly(e))


def _line(event):
    return json.dumps(event, default=str) + "\n"


@app.post("/api/ask")
def ask(body: Ask, request: Request):
    question = " ".join(body.question.split())
    if not question:
        raise HTTPException(400, "Please type a question.")
    if len(question) > MAX_CHARS:
        raise HTTPException(400, f"Please keep the question under {MAX_CHARS} characters.")
    if not limiter.allow(_source(request)):
        raise HTTPException(429, "Too many questions in a minute. Please wait a moment and try again.")

    hit = cache.get(question)

    def stream():
        if hit:
            for event in hit["events"]:
                yield _line(event)
            yield _line({**hit["result"], "type": "result", "cached": True})
            return
        if not daily.take():
            yield _line({"type": "error", "message": "The daily question limit has been reached. Please try again tomorrow."})
            return

        out, events = queue.Queue(), []

        def emit(event):
            events.append(event)
            out.put(event)

        def work():
            try:
                result = run_team(question, emit=emit)
                result["chart"] = best_chart(result["findings"])
                result["backend"] = {"data": config.DATA_BACKEND, "llm": config.LLM_BACKEND}
                cache.put(question, {"events": list(events), "result": result})
                out.put({**result, "type": "result", "cached": False})
            except Exception as e:  # noqa: BLE001
                out.put({"type": "error", "message": _friendly(e)})
            finally:
                out.put(None)

        threading.Thread(target=work, daemon=True).start()
        while True:
            try:
                event = out.get(timeout=180)
            except queue.Empty:
                yield _line({"type": "error", "message": "The team took too long. Please try again."})
                return
            if event is None:
                return
            yield _line(event)

    return StreamingResponse(stream(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


# The website itself (registered last so /api routes win)
WEB = ROOT / "web"
if WEB.exists():
    app.mount("/", StaticFiles(directory=WEB, html=True), name="web")
