# WEB LAYER: takes the user's question from the browser, adds it to that session's
# conversation history, hands both to the fraud agent, and returns the answer as JSON.

from datetime import date
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# REQUIREMENT: agents/ is a plain folder, not an installed package, so put the
# project root on the import path before importing the agent.
sys.path.insert(0, str(Path(__file__).parent))
from agents.orchestrator import run

app = FastAPI()

# REQUIREMENT: hold each session's turns so a follow-up like "yes, open it" still
# knows what was offered. Plain dict in memory — fine for a demo, and it empties
# every time the server restarts. Swap for Redis before anything real.
SESSIONS: dict[str, list] = {}

# REQUIREMENT: this box is open to the internet and every question costs API credit,
# so cap the whole app rather than per user. Counter resets at midnight, and also
# whenever the server restarts.
DAILY_LIMIT = 10
_usage = {"date": None, "count": 0}


def _over_limit() -> bool:
    today = date.today().isoformat()

    if _usage["date"] != today:
        _usage["date"] = today
        _usage["count"] = 0

    _usage["count"] += 1
    return _usage["count"] > DAILY_LIMIT

class Question(BaseModel):
    question: str
    session_id: str = "default"


class Session(BaseModel):
    session_id: str = "default"


@app.post("/ask")
async def ask(q: Question):
    if _over_limit():
        return {"answer": f"Daily limit of {DAILY_LIMIT} questions reached. Try again tomorrow."}    
    history = SESSIONS.get(q.session_id, [])
    # REQUEST OUT: hand the question plus prior turns to the agent loop.
    answer, history = await run(q.question, history)
    # RESPONSE IN: the agent's final text, plus the conversation to carry forward.
    SESSIONS[q.session_id] = history
    return {"answer": answer}


@app.post("/reset")
async def reset(s: Session):
    SESSIONS.pop(s.session_id, None)
    return {"ok": True}

# Serves static/index.html at "/" — keep this last so /ask isn't shadowed.
app.mount("/", StaticFiles(directory="static", html=True), name="static")