from .verify import verify
import json
import re
from .db import query
from .guard import clean_sql
from .llm import llm
from .prompts import data_notes, schema_text, sql_system


def plan(question):
    out = llm(
        "You are a planner for a data team. Break the client's question into 1 to 3 short "
        "sub-questions phrased as clear business questions. Do NOT write SQL and do NOT mention table or "
        "column names. Each sub-question must be answerable by one query. If the question is "
        "simple, return it unchanged as the only item. If the question asks for an overall "
        "figure AND a breakdown (for example how revenue changed and which category drove it), "
        "return exactly two sub-questions: one for the overall total in each period with the "
        "difference, and one for the breakdown by group in each period with the difference. "
        "If the question links two things (for example months and products), keep them in ONE "
        "sub-question so the results stay connected. "
        "Example: for 'which months and which products earned the most revenue' return ONE "
        'sub-question: ["The top 5 months by revenue, each with its top product and that '
        'product\'s revenue"]. '
        "If the client asks for several details about the top N items, make it ONE sub-question "
        "that asks for all the details together. "
        "The data has no cost or profit information. If the client asks for profit, margin or "
        "cost, replace it with net sales (sales after discounts) in the sub-question. "
        f"Data notes:{data_notes()}\n"
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

def write_answer(question, findings, problems=None):
    extra = ""
    if problems:
        extra = ("\nYour previous answer had these problems. Fix them:\n- "
                 + "\n- ".join(problems))
    return llm(
        "You are a senior analyst on a data team, writing a professional briefing for a "
        "business stakeholder. Use a concise, formal tone. Lead with the answer. "
        "Only if the question explicitly asks for something the data does not contain "
        "(the data has no cost or profit information), say so in the first sentence "
        "and state which metric you used instead. Otherwise do not mention data limitations, "
        "and never say the data cannot provide something that appears in the findings. "
        "Quote key figures in USD with thousands separators (for example $3,091.93), and "
        "give percentage changes when comparing periods. Include every figure the findings "
        "provide for each item, such as both a month's total revenue and its top product's "
        "revenue. State the time period only from the years and months that appear in the "
        "findings; if no period was asked for, say the answer covers all available data. "
        "Never say a figure applies to a period unless the findings show it. "
        "Copy every dollar amount exactly as it appears in the findings; never rescale or "
        "move a decimal point. Keep it under 150 words and never invent numbers that are "
        "not in the findings. If a finding was not approved by the reviewer, say it is less certain.",
        f"Client question: {question}\nFindings: {json.dumps(findings, default=str)}\n"
        f"Data notes: {data_notes()}{extra}", max_tokens=800)

def team(question):
    print("QUESTION:", question)
    subs = plan(question)
    print("PLANNER ->", subs, "\n")
    findings = []
    for sq in subs:
        feedback, prev_sql = None, None
        for attempt in range(3):
            try:
                sql, names, rows = analyst(sq, feedback, prev_sql)
            except Exception as e:
                feedback = f"query failed: {str(e)[:200]}"
                print(f"ANALYST (try {attempt + 1}) failed: {feedback}")
                continue
            verdict = reviewer(sq, sql, names, rows)
            print(f"ANALYST  -> {sq}\n  SQL: {' '.join(sql.split())}\nREVIEWER -> {verdict}\n")
            if verdict.upper().startswith("OK") or attempt == 2:
                findings.append({"question": sq, "columns": names,
                                 "rows": rows[:20], "reviewer": verdict})
                break
            feedback, prev_sql = verdict, sql

    answer = write_answer(question, findings)
    problems = verify(question, findings, answer)
    for _ in range(2):
        if not problems:
            break
        print("ANSWER REVIEWER ->", problems, "\n")
        answer = write_answer(question, findings, problems)
        problems = verify(question, findings, answer)
    if problems:
        print("ANSWER REVIEWER ->", problems, "\n")
        answer += "\n\nNote: this answer could not be fully verified: " + " ".join(problems)
    return answer