from functools import lru_cache
from .config import CATALOG as C, SCHEMA as S
from .db import query


@lru_cache(maxsize=1)
def data_notes():
    latest = query(f"SELECT MAX(order_date) FROM {C}.{S}.clean_orders")[1][0][0]
    return f"""
- Amounts are in USD. Revenue ALWAYS means SUM(total_amount_usd) from clean_orders. Never use subtotal_usd for revenue.
- Use clean_orders for revenue and order counts. Use order_date for anything over time.
- Do NOT use registration_date for tenure or signup cohorts: most orders predate it (data quirk).
- clean_monthly_revenue and clean_product_summary are pre-aggregated; prefer clean_orders for custom cuts.
- The latest order in the data is {latest}. For relative periods ("last 12 months", "this year", "recently"), anchor to {latest}, never CURRENT_DATE. Example: last 12 months = order_date > DATE_ADD('{latest}', -365).
- When the question gives explicit years or dates, use exactly those.
- Only for "best seller" questions: rank by SUM(quantity) and also return SUM(total_amount_usd). For every other question, sort by the metric asked about and return only the columns needed.
- For "top" questions return the number of rows asked for; if no number is given, return 5.
- For "change", "growth", "compare" or "drove" questions, return one row per group with a column per period plus the difference. Order by ABS(difference) DESC and return the top 3, so both big gains and big drops show.
"""


@lru_cache(maxsize=1)
def sql_system():
    _, cols = query(f"""SELECT table_name, column_name, data_type
                        FROM {C}.information_schema.columns
                        WHERE table_schema = '{S}' AND table_name LIKE 'clean_%'
                        ORDER BY table_name, ordinal_position""")
    schema = {}
    for t, c, d in cols:
        schema.setdefault(t, []).append(f"{c} ({d})")
    schema_text = "\n".join(f"{C}.{S}.{t}: " + ", ".join(cs) for t, cs in schema.items())
    return f"""You write Databricks SQL for a business analyst agent.
Tables:
{schema_text}
Notes:{data_notes()}
Return ONLY one SELECT query, no explanation, no markdown."""
