"""
Unghosted scoring model.

Two modes:
  - RULE-BASED (default): a transparent, hand-weighted score. Use this for
    the demo until you have enough real call outcomes.
  - LEARNED: a logistic regression trained on your own call_logs +
    user_reports, once you have ~30+ labeled outcomes. Falls back to
    rule-based automatically if there isn't enough data yet.

Score is 0-100: higher = more likely this listing is real, open, and worth
calling first. Every score comes with a short plain-English reason, because
that reason line is what the judges (and users) actually read.

Run standalone to rescore everything in the DB:
    python3 scoring.py
"""

import sqlite3
from collections import Counter

DB_PATH = "unghosted.db"
MIN_LABELED_FOR_ML = 30  # below this, always use rule-based scoring

# --- Rule-based weights -----------------------------------------------

BASE_SCORE = 50

CALL_OUTCOME_WEIGHTS = {
    "booked": 40,
    "accepting": 30,
    "voicemail_vague": -10,
    "no_answer": -25,
    "not_accepting": -45,
    "wrong_number": -60,
}

USER_REPORT_WEIGHTS = {
    "booked": 15,
    "accepting": 10,
    "wrong_number": -30,
    "not_accepting": -30,
    "no_answer": -10,
}

NPI_ADDRESS_MATCH_BONUS = 15
NPI_ADDRESS_MISMATCH_PENALTY = -20
CLAIMED_NOT_ACCEPTING_PENALTY = -50
DUPLICATE_LISTING_PENALTY_PER_EXTRA = -8  # per additional listing sharing an address/phone
MAX_DUPLICATE_PENALTY = -32


def _clamp(score):
    return max(0, min(100, round(score)))


def score_provider_rule_based(provider_row, call_outcomes, report_outcomes):
    """
    provider_row: sqlite3.Row from the providers table
    call_outcomes: list of outcome strings from call_logs for this provider
    report_outcomes: list of outcome strings from user_reports for this provider
    Returns (score:int, reason:str)
    """
    score = BASE_SCORE
    reasons = []

    if provider_row["accepting_new_patients_claimed"] == 0:
        score += CLAIMED_NOT_ACCEPTING_PENALTY
        reasons.append("directory says not accepting new patients")

    # Most recent call outcome matters most; average the rest lightly.
    if call_outcomes:
        latest = call_outcomes[-1]
        score += CALL_OUTCOME_WEIGHTS.get(latest, 0)
        if latest == "booked":
            reasons.append("we booked an appointment here")
        elif latest == "accepting":
            reasons.append("confirmed accepting new patients")
        elif latest == "not_accepting":
            reasons.append("confirmed NOT accepting new patients")
        elif latest == "wrong_number":
            reasons.append("number was wrong or disconnected")
        elif latest == "no_answer":
            reasons.append("no answer when we called")
        elif latest == "voicemail_vague":
            reasons.append("reached voicemail, no useful info")

    if report_outcomes:
        counts = Counter(report_outcomes)
        for outcome, weight in USER_REPORT_WEIGHTS.items():
            n = counts.get(outcome, 0)
            if n:
                score += weight * min(n, 3) / max(1, min(n, 3))  # weight applies per-signal, capped influence
        top_outcome, top_n = counts.most_common(1)[0]
        reasons.append(f"{top_n} user report(s): {top_outcome.replace('_', ' ')}")

    npi_match = provider_row["npi_address_match"]
    if npi_match == 1:
        score += NPI_ADDRESS_MATCH_BONUS
        reasons.append("NPI registry confirms address")
    elif npi_match == 0:
        score += NPI_ADDRESS_MISMATCH_PENALTY
        reasons.append("NPI registry address mismatch")

    dup_count = provider_row["duplicate_listing_count"] or 0
    if dup_count > 0:
        penalty = max(MAX_DUPLICATE_PENALTY, DUPLICATE_LISTING_PENALTY_PER_EXTRA * dup_count)
        score += penalty
        reasons.append(f"listed at {dup_count + 1} locations")

    if not reasons:
        reasons.append("no verification signals yet — unverified directory listing")

    return _clamp(score), "; ".join(reasons[:2])  # keep the UI reason line short


def score_provider_ml(provider_row, call_outcomes, report_outcomes, model):
    """
    Logistic regression path. `model` is a fitted sklearn LogisticRegression
    (see train_model()). Falls back to rule-based reason text for
    explainability since a raw coefficient dump isn't demo-friendly.
    """
    features = _extract_features(provider_row, call_outcomes, report_outcomes)
    proba = model.predict_proba([features])[0][1]  # P(real & open)
    score = _clamp(proba * 100)
    # Still show a human reason using the rule-based logic for the UI.
    _, reason = score_provider_rule_based(provider_row, call_outcomes, report_outcomes)
    return score, reason


def _extract_features(provider_row, call_outcomes, report_outcomes):
    latest_call = call_outcomes[-1] if call_outcomes else "none"
    call_map = {"booked": 4, "accepting": 3, "voicemail_vague": 1, "no_answer": 0,
                "not_accepting": -2, "wrong_number": -3, "none": 0}
    report_score = sum(USER_REPORT_WEIGHTS.get(o, 0) for o in report_outcomes)
    return [
        provider_row["accepting_new_patients_claimed"],
        call_map.get(latest_call, 0),
        report_score,
        provider_row["npi_address_match"] if provider_row["npi_address_match"] is not None else -1,
        provider_row["duplicate_listing_count"] or 0,
    ]


def train_model(conn):
    """
    Trains a logistic regression on providers that have at least one call
    outcome, labeling 'booked'/'accepting' as positive (1) and
    'not_accepting'/'wrong_number' as negative (0). Returns None if there
    isn't enough labeled data yet.
    """
    try:
        from sklearn.linear_model import LogisticRegression
    except ImportError:
        print("scikit-learn not installed (pip install --break-system-packages scikit-learn); using rule-based scoring")
        return None

    cur = conn.cursor()
    cur.execute("SELECT * FROM providers")
    providers = cur.fetchall()

    X, y = [], []
    for p in providers:
        calls = _get_call_outcomes(conn, p["id"])
        if not calls:
            continue
        latest = calls[-1]
        if latest in ("booked", "accepting"):
            label = 1
        elif latest in ("not_accepting", "wrong_number"):
            label = 0
        else:
            continue  # ambiguous outcomes (no_answer, voicemail_vague) aren't used as training labels
        reports = _get_report_outcomes(conn, p["id"])
        X.append(_extract_features(p, calls, reports))
        y.append(label)

    if len(X) < MIN_LABELED_FOR_ML or len(set(y)) < 2:
        print(f"Only {len(X)} labeled examples (need {MIN_LABELED_FOR_ML}+, both classes) — using rule-based scoring")
        return None

    model = LogisticRegression()
    model.fit(X, y)
    print(f"Trained logistic regression on {len(X)} labeled calls")
    return model


def _get_call_outcomes(conn, provider_id):
    cur = conn.cursor()
    cur.execute(
        "SELECT outcome FROM call_logs WHERE provider_id = ? ORDER BY called_at", (provider_id,)
    )
    return [r["outcome"] for r in cur.fetchall()]


def _get_report_outcomes(conn, provider_id):
    cur = conn.cursor()
    cur.execute(
        "SELECT outcome FROM user_reports WHERE provider_id = ? ORDER BY reported_at", (provider_id,)
    )
    return [r["outcome"] for r in cur.fetchall()]


def refresh_verified_waits(conn):
    """
    Sets providers.verified_wait_days to the most recent REAL wait we've
    observed: either a team call that got an appointment offer
    (call_logs.actual_wait_days) or a user who booked and told us how far
    out it was (user_reports.wait_days). This is the "We found" number that
    sits next to CBH's self-reported "CBH says" number.
    """
    conn.execute(
        """
        UPDATE providers SET verified_wait_days = (
            SELECT wait FROM (
                SELECT actual_wait_days AS wait, called_at AS ts
                  FROM call_logs
                 WHERE provider_id = providers.id AND actual_wait_days IS NOT NULL
                UNION ALL
                SELECT wait_days AS wait, reported_at AS ts
                  FROM user_reports
                 WHERE provider_id = providers.id AND wait_days IS NOT NULL
            )
            ORDER BY ts DESC
            LIMIT 1
        )
        """
    )


def rescore_all():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    refresh_verified_waits(conn)
    model = train_model(conn)

    cur.execute("SELECT * FROM providers")
    providers = cur.fetchall()

    for p in providers:
        calls = _get_call_outcomes(conn, p["id"])
        reports = _get_report_outcomes(conn, p["id"])
        if model is not None:
            score, reason = score_provider_ml(p, calls, reports, model)
        else:
            score, reason = score_provider_rule_based(p, calls, reports)
        conn.execute(
            "UPDATE providers SET score = ?, score_reason = ?, updated_at = datetime('now') WHERE id = ?",
            (score, reason, p["id"]),
        )

    conn.commit()
    conn.close()
    print(f"Rescored {len(providers)} providers ({'ML' if model else 'rule-based'} mode)")


if __name__ == "__main__":
    rescore_all()
