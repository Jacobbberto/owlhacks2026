"""
Unghosted backend API.

Run:
    pip install --break-system-packages fastapi uvicorn
    python3 seed_data.py          # first time only, or after resetting DB
    uvicorn main:app --reload --port 8000

Then open frontend/index.html (it calls http://localhost:8000 by default).
"""

import sqlite3
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from scoring import rescore_all

DB_PATH = "unghosted.db"

app = FastAPI(title="Unghosted API")

# Wide open for hackathon purposes — tighten before this ever sees real users.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


class ReportIn(BaseModel):
    outcome: str  # 'booked' | 'not_accepting' | 'wrong_number' | 'no_answer'
    wait_days: Optional[int] = None  # for 'booked': days until the appointment


VALID_REPORT_OUTCOMES = {"booked", "not_accepting", "wrong_number", "no_answer"}


@app.get("/")
def root():
    return {"service": "unghosted", "status": "ok"}


@app.get("/providers/search")
def search_providers(
    zip_code: Optional[str] = None,
    specialty: Optional[str] = None,
    language: Optional[str] = None,
    sort: str = "score",  # 'score' (most reliable first) | 'wait' (soonest available first)
    limit: int = 3,
):
    """
    Returns the top-N providers, optionally filtered by zip code, specialty
    keyword, or spoken language. This is the endpoint the "Maya searches"
    screen calls.

    sort='score' (default): most likely to be real and open first. This is
      the ghost-network fix — barrier #3, "the match game."
    sort='wait': shortest reported wait first, among providers with a
      score >= 35 (i.e. we don't recommend racing to a probable ghost just
      because it claims a short wait). This surfaces barrier #2, the
      hidden-waitlist problem, instead of leaving it buried in a PDF.
    """
    conn = get_conn()
    query = "SELECT * FROM providers WHERE 1=1"
    params = []

    if zip_code:
        query += " AND zip_code = ?"
        params.append(zip_code)
    if specialty:
        query += " AND specialty LIKE ?"
        params.append(f"%{specialty}%")
    if language:
        query += " AND languages LIKE ?"
        params.append(f"%{language}%")

    if sort == "wait":
        # Prefer the wait we actually observed over the one CBH claims.
        query += " AND score >= 35 AND COALESCE(verified_wait_days, reported_wait_days) IS NOT NULL"
        query += " ORDER BY COALESCE(verified_wait_days, reported_wait_days) ASC, score DESC LIMIT ?"
    else:
        query += " ORDER BY score DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(query, params).fetchall()
    conn.close()

    return [dict(r) for r in rows]


@app.get("/stats")
def stats(zip_code: Optional[str] = None):
    """
    Powers the "claimed vs. real" stat card.

    The comparison only uses providers where we have BOTH numbers (CBH's
    self-reported wait and a wait we actually observed), so it's an
    apples-to-apples gap, not two averages over different providers.

    If nothing has been verified yet, falls back to the claimed average
    among providers scoring >= 35, and says so.
    """
    conn = get_conn()
    zip_clause = " AND zip_code = ?" if zip_code else ""
    params = [zip_code] if zip_code else []

    compared = conn.execute(
        f"""
        SELECT AVG(reported_wait_days) AS claimed,
               AVG(verified_wait_days) AS verified,
               COUNT(*) AS n
          FROM providers
         WHERE reported_wait_days IS NOT NULL
           AND verified_wait_days IS NOT NULL{zip_clause}
        """,
        params,
    ).fetchone()

    claimed_only = conn.execute(
        f"""
        SELECT AVG(reported_wait_days) AS claimed, COUNT(*) AS n
          FROM providers
         WHERE score >= 35 AND reported_wait_days IS NOT NULL{zip_clause}
        """,
        params,
    ).fetchone()

    total = conn.execute(
        f"SELECT COUNT(*) AS c FROM providers WHERE 1=1{zip_clause}", params
    ).fetchone()["c"]
    conn.close()

    def r(x):
        return round(x, 1) if x is not None else None

    return {
        "compared_provider_count": compared["n"],
        "claimed_avg_wait_days": r(compared["claimed"]),
        "verified_avg_wait_days": r(compared["verified"]),
        "fallback_claimed_avg_wait_days": r(claimed_only["claimed"]),
        "fallback_provider_count": claimed_only["n"],
        "total_provider_count": total,
    }


@app.get("/providers/{provider_id}")
def get_provider(provider_id: int):
    conn = get_conn()
    row = conn.execute("SELECT * FROM providers WHERE id = ?", (provider_id,)).fetchone()
    conn.close()
    if not row:
        raise HTTPException(status_code=404, detail="provider not found")
    return dict(row)


@app.post("/providers/{provider_id}/report")
def report_outcome(provider_id: int, report: ReportIn):
    """
    The one-tap 'what happened when you called' button. This is the
    crowdsourced correction loop: every report here feeds back into the
    score the next person sees.
    """
    if report.outcome not in VALID_REPORT_OUTCOMES:
        raise HTTPException(
            status_code=400,
            detail=f"outcome must be one of {sorted(VALID_REPORT_OUTCOMES)}",
        )
    if report.wait_days is not None:
        if report.outcome != "booked":
            raise HTTPException(status_code=400, detail="wait_days only applies to 'booked' reports")
        if not 0 <= report.wait_days <= 365:
            raise HTTPException(status_code=400, detail="wait_days must be between 0 and 365")

    conn = get_conn()
    exists = conn.execute("SELECT id FROM providers WHERE id = ?", (provider_id,)).fetchone()
    if not exists:
        conn.close()
        raise HTTPException(status_code=404, detail="provider not found")

    conn.execute(
        "INSERT INTO user_reports (provider_id, outcome, wait_days) VALUES (?, ?, ?)",
        (provider_id, report.outcome, report.wait_days),
    )
    conn.commit()
    conn.close()

    # Rescore immediately so a live demo shows the number move.
    rescore_all()

    conn = get_conn()
    updated = conn.execute("SELECT * FROM providers WHERE id = ?", (provider_id,)).fetchone()
    conn.close()
    return dict(updated)


@app.get("/providers")
def list_all_providers():
    conn = get_conn()
    rows = conn.execute("SELECT * FROM providers ORDER BY score DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]
