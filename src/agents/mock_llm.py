"""A scripted stand-in for the language model, so the whole project runs with no account and no cost.

It does not understand language. It recognises a handful of question types by keyword and
answers with real SQL that runs on the real data. Anything else gets a clearly labelled
fallback. Use LLM_BACKEND=databricks or anthropic for open-ended questions.
"""
import json
import re

T = "workspace.ai_data_team.clean_orders"
CU = "workspace.ai_data_team.clean_customers"

# (keywords that must all appear, SQL)
SQL_BOOK = [
    (["total", "difference"], f"""WITH t AS (SELECT
        SUM(CASE WHEN year = 2024 THEN total_amount_usd END) AS revenue_2024,
        SUM(CASE WHEN year = 2025 THEN total_amount_usd END) AS revenue_2025 FROM {T})
        SELECT ROUND(revenue_2024, 2) AS revenue_2024, ROUND(revenue_2025, 2) AS revenue_2025,
               ROUND(revenue_2025 - revenue_2024, 2) AS difference,
               ROUND((revenue_2025 - revenue_2024) * 100.0 / revenue_2024, 1) AS pct_change FROM t"""),
    (["category", "difference"], f"""WITH c AS (SELECT category,
        SUM(CASE WHEN year = 2024 THEN total_amount_usd END) AS revenue_2024,
        SUM(CASE WHEN year = 2025 THEN total_amount_usd END) AS revenue_2025 FROM {T} GROUP BY category)
        SELECT category, ROUND(revenue_2024, 2) AS revenue_2024, ROUND(revenue_2025, 2) AS revenue_2025,
               ROUND(revenue_2025 - revenue_2024, 2) AS difference
        FROM c ORDER BY ABS(revenue_2025 - revenue_2024) DESC LIMIT 3"""),
    (["deepest"], f"""WITH m AS (SELECT year, month, SUM(total_amount_usd) AS revenue FROM {T} GROUP BY year, month),
        d AS (SELECT year, month, revenue, revenue - LAG(revenue) OVER (ORDER BY year, month) AS change FROM m),
        r AS (SELECT *, ROW_NUMBER() OVER (PARTITION BY year ORDER BY change ASC) AS rn FROM d WHERE change < 0)
        SELECT year, month, ROUND(revenue, 2) AS revenue, ROUND(change, 2) AS change FROM r WHERE rn = 1 ORDER BY year"""),
    (["last 12 months"], f"""WITH l AS (SELECT MAX(order_date) AS d FROM {T})
        SELECT ROUND(SUM(CASE WHEN order_date > DATE_ADD(l.d, -365) THEN total_amount_usd END), 2) AS last_12_months,
               ROUND(SUM(CASE WHEN order_date > DATE_ADD(l.d, -730) AND order_date <= DATE_ADD(l.d, -365) THEN total_amount_usd END), 2) AS previous_12_months
        FROM {T}, l"""),
    (["product"], f"""SELECT product_name, ROUND(SUM(total_amount_usd), 2) AS revenue, SUM(quantity) AS units
        FROM {T} GROUP BY product_name ORDER BY revenue DESC LIMIT 5"""),
    (["channel"], f"""SELECT c.acquisition_channel, ROUND(SUM(o.total_amount_usd), 2) AS revenue, COUNT(*) AS orders
        FROM {T} o JOIN {CU} c USING (customer_id) GROUP BY c.acquisition_channel ORDER BY revenue DESC"""),
    (["tier"], f"""SELECT c.membership_tier, ROUND(SUM(o.total_amount_usd), 2) AS revenue, COUNT(*) AS orders
        FROM {T} o JOIN {CU} c USING (customer_id) GROUP BY c.membership_tier ORDER BY revenue DESC"""),
    (["return"], f"""SELECT category, ROUND(AVG(returned) * 100, 1) AS return_rate_pct, COUNT(*) AS orders
        FROM {T} GROUP BY category ORDER BY return_rate_pct DESC LIMIT 5"""),
    (["category"], f"""SELECT category, ROUND(SUM(total_amount_usd), 2) AS revenue FROM {T}
        GROUP BY category ORDER BY revenue DESC LIMIT 5"""),
]
FALLBACK_SQL = f"""SELECT year, ROUND(SUM(total_amount_usd), 2) AS revenue, COUNT(*) AS orders
        FROM {T} GROUP BY year ORDER BY year"""

# Phrases that map a free-text question onto the keywords above
ALIASES = {
    "deepest": ["deepest", "biggest drop", "largest drop", "month-over-month drop"],
    "last 12 months": ["last 12 months", "last year", "past year", "past 12 months", "recent"],
    "product": ["product", "best seller", "bestseller", "top sell", "best-sell"],
    "channel": ["channel", "acquisition", "acquired", "marketing"],
    "tier": ["tier", "membership", "loyalty"],
    "return": ["return"],
    "category": ["category", "categories"],
}


def _sql_for(text):
    t = text.lower()
    for keys, sql in SQL_BOOK:
        if all(k in t or any(a in t for a in ALIASES.get(k, [])) for k in keys):
            return sql
    return FALLBACK_SQL


def _plan(question):
    q = question.lower()
    if "category" in q and ("change" in q or "drove" in q or "driver" in q or "growth" in q):
        return ["Total revenue in 2024 and 2025, with the difference",
                "Revenue by category in 2024 and 2025, with the difference"]
    return [question]


def _write(user):
    m = re.search(r"Findings: (\[.*\])\nData notes", user, re.S)
    findings = json.loads(m.group(1)) if m else []
    q = re.search(r"Client question: (.*)\nFindings", user, re.S)
    lines = ["(Mock model: this answer is a template over the real query results, not written by an AI.)"]
    for f in findings:
        cols, rows = f["columns"], f["rows"]
        if not rows:
            lines.append("No rows came back for this part of the question.")
            continue
        shown = []
        for r in rows[:8]:
            shown.append(", ".join(f"{c} {v}" for c, v in zip(cols, r)))
        lines.append(f"{f['question']}: " + "; ".join(shown) + ".")
    return " ".join(lines)


def respond(system, user):
    s = system.lstrip()
    if s.startswith("You are a planner"):
        return json.dumps(_plan(user))
    if s.startswith("You write Databricks SQL"):
        return _sql_for(user.split("\n")[0])
    if s.startswith("You review SQL"):
        return "OK"
    if s.startswith("You are the writer"):
        return _write(user)
    return "OK"
