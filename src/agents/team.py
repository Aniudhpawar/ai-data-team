import json
import re
from .db import query
from .guard import clean_sql
from .llm import llm
from .prompts import data_notes, sql_system


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

def analyst(subq, feedback=None):
    q = subq if not feedback else (
        f"{subq}\nA reviewer rejected your previous SQL: {feedback}. Fix it.")
    sql = clean_sql(llm(sql_system(), q))
    names, rows = query(f"SELECT * FROM ({sql}) LIMIT 200")
    return sql, names, rows


def reviewer(subq, sql, names, rows):
    return llm(
        "You review SQL written for a data analyst. Reply FIX only if the SQL breaks one of "
        "these rules or fails to answer the question (wrong period, wrong metric, wrong grouping). "
        "Extra columns are fine and are NOT a reason to reject.\n"
        f"{data_notes()}\nReply with exactly 'OK' or 'FIX: <one sentence>'.",
        f"Question: {subq}\nSQL: {sql}\nColumns: {names}\nFirst rows: {rows[:5]}",
        max_tokens=100).strip()


def team(question):
    print("QUESTION:", question)
    subs = plan(question)
    print("PLANNER ->", subs, "\n")
    findings = []
    for sq in subs:
        feedback = None
        for attempt in range(2):
            try:
                sql, names, rows = analyst(sq, feedback)
            except Exception as e:
                feedback = f"query failed: {str(e)[:200]}"
                print(f"ANALYST (try {attempt + 1}) failed: {feedback}")
                continue
            verdict = reviewer(sq, sql, names, rows)
            print(f"ANALYST  -> {sq}\n  SQL: {' '.join(sql.split())}\nREVIEWER -> {verdict}\n")
            if verdict.upper().startswith("OK") or attempt == 1:
                findings.append({"question": sq, "columns": names,
                                 "rows": rows[:20], "reviewer": verdict})
                break
            feedback = verdict
    return llm(
        "You are the writer on a data team, explaining findings to a non-technical business "
        "client. Use plain English, lead with the answer, always state the time period, quote "
        "key numbers in USD, and give percentage changes when comparing periods. Keep it under "
        "150 words and never invent numbers that are not in the findings. If a finding was not "
        "approved by the reviewer, say it is less certain.",
        f"Client question: {question}\nFindings: {json.dumps(findings, default=str)}\n"
        f"Data notes: {data_notes()}", max_tokens=500)

