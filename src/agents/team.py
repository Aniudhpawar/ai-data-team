import json
import re
import time
from .db import query
from .guard import clean_sql
from .llm import llm
from .prompts import data_notes, schema_text, sql_system


def plan(question):
    out = llm(
        "You are a planner for a data team. Break the client's question into 1 to 3 short "
        "sub-questions written in plain English. Do NOT write SQL and do NOT mention table or "
        "column names. Each sub-question must be answerable by one query. If the question is "
        "simple, return it unchanged as the only item. If the question asks for an overall "
        "figure AND a breakdown (for example how revenue changed and which category drove it), "
        "return exactly two sub-questions: one for the overall total in each period with the "
        "difference, and one for the breakdown by group in each period with the difference. "
        'Reply with ONLY a JSON list of strings. Example: ["Total revenue in 2024 and 2025, with the difference", "Revenue by category in 2024 and 2025, with the difference"]',
        question)
    try:
        subs = json.loads(re.search(r"\[.*\]", out, re.S).group(0))
        return [s for s in subs if isinstance(s, str)][:3] or [question]
    except Exception:
        return [question]


def analyst(subq, feedback=None, prev_sql=None):
    q = subq
    if feedback:
        q = (f"{subq}\nYour previous SQL was:\n{prev_sql or '(none)'}\n"
             f"It was rejected: {feedback}\nWrite a corrected query.")
    sql = clean_sql(llm(sql_system(), q))
    names, rows = query(f"SELECT * FROM ({sql}) LIMIT 200")
    return sql, names, rows


def reviewer(subq, sql, names, rows):
    return llm(
        "You review SQL written for a data analyst. Reply FIX only if the SQL breaks one of "
        "these rules, uses a column or table that does not exist, or fails to answer the "
        "question (wrong period, wrong metric, wrong grouping). "
        "Extra columns are fine and are NOT a reason to reject.\n"
        f"Available tables and columns:\n{schema_text()}\n"
        f"Rules:{data_notes()}\nReply with exactly 'OK' or 'FIX: <one sentence>'.",
        f"Question: {subq}\nSQL: {sql}\nColumns: {names}\nFirst rows: {rows[:5]}",
        max_tokens=100).strip()


def writer(question, findings):
    return llm(
        "You are the writer on a data team, explaining findings to a non-technical business "
        "client. Use plain English, lead with the answer, always state the time period, quote "
        "key numbers in USD, and give percentage changes when comparing periods. "
        "Copy every dollar amount exactly as it appears in the findings; never round, rescale "
        "or move a decimal point. Keep it under 150 words and never invent numbers that are "
        "not in the findings. If a finding was not approved by the reviewer, say it is less certain.",
        f"Client question: {question}\nFindings: {json.dumps(findings, default=str)}\n"
        f"Data notes: {data_notes()}", max_tokens=500)


def run_team(question, emit=None):
    """Run the team and return everything the website needs.

    Same Planner -> Analyst -> Reviewer -> Writer logic as before. `emit(event)` is called
    after each step so a caller can stream progress. Returns a dict with the answer, the
    findings (including the SQL used) and the time taken.
    """
    emit = emit or (lambda event: None)
    started = time.time()
    emit({"type": "question", "text": question})
    subs = plan(question)
    emit({"type": "plan", "subquestions": subs})
    findings, details = [], []
    for sq in subs:
        feedback, prev_sql = None, None
        for attempt in range(3):
            try:
                sql, names, rows = analyst(sq, feedback, prev_sql)
            except Exception as e:
                feedback = f"query failed: {str(e)[:200]}"
                emit({"type": "analyst_failed", "question": sq, "attempt": attempt + 1,
                      "error": feedback})
                continue
            emit({"type": "analyst", "question": sq, "attempt": attempt + 1, "sql": sql,
                  "columns": names, "row_count": len(rows)})
            verdict = reviewer(sq, sql, names, rows)
            emit({"type": "review", "question": sq, "attempt": attempt + 1,
                  "verdict": verdict, "approved": verdict.upper().startswith("OK")})
            if verdict.upper().startswith("OK") or attempt == 2:
                # What the writer sees is unchanged; the SQL is kept separately for display.
                findings.append({"question": sq, "columns": names,
                                 "rows": rows[:20], "reviewer": verdict})
                details.append({"question": sq, "sql": sql, "columns": names,
                                "rows": rows[:20], "reviewer": verdict})
                break
            feedback, prev_sql = verdict, sql
    emit({"type": "writing"})
    answer = writer(question, findings)
    return {"question": question, "subquestions": subs, "findings": details,
            "answer": answer, "seconds": round(time.time() - started, 1)}


def _console(event):
    """Print progress exactly as the original command-line version did."""
    t = event["type"]
    if t == "question":
        print("QUESTION:", event["text"])
    elif t == "plan":
        print("PLANNER ->", event["subquestions"], "\n")
    elif t == "analyst_failed":
        print(f"ANALYST (try {event['attempt']}) failed: {event['error']}")
    elif t == "analyst":
        print(f"ANALYST  -> {event['question']}\n  SQL: {' '.join(event['sql'].split())}")
    elif t == "review":
        print(f"REVIEWER -> {event['verdict']}\n")


def team(question):
    return run_team(question, emit=_console)["answer"]
