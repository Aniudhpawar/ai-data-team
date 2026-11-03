from functools import lru_cache
from .config import CATALOG as C, SCHEMA as S
from .db import query


@lru_cache(maxsize=1)
def data_notes():
    latest = query(f"SELECT MAX(order_date) FROM {C}.{S}.clean_orders")[1][0][0]
    return f"""
- Always ROUND money to 2 decimals and percentages to 1 decimal in SQL.
- If a question mentions two dimensions (for example months and products), answer it in ONE query so each product is tied to its month. Month alone is ambiguous across years, so always include year.
- "Top products in the top months": rank months by revenue, keep the top 5 (or N asked), then take the top product within each of those months. Never return more than 10 rows for such questions. Example: WITH m AS (SELECT year, month, SUM(total_amount_usd) AS month_revenue FROM workspace.ai_data_team.clean_orders GROUP BY year, month), top_m AS (SELECT * FROM m ORDER BY month_revenue DESC LIMIT 5), p AS (SELECT year, month, product_name, SUM(total_amount_usd) AS product_revenue, ROW_NUMBER() OVER (PARTITION BY year, month ORDER BY SUM(total_amount_usd) DESC) AS rn FROM workspace.ai_data_team.clean_orders GROUP BY year, month, product_name) SELECT t.year, t.month, ROUND(t.month_revenue, 2) AS month_revenue, p.product_name, ROUND(p.product_revenue, 2) AS product_revenue FROM top_m t JOIN p ON t.year = p.year AND t.month = p.month WHERE p.rn = 1 ORDER BY t.month_revenue DESC
- If the question does not give a time period, use all data and say so.
"""


@lru_cache(maxsize=1)
def schema_text():
    _, cols = query(f"""SELECT table_name, column_name, data_type
                        FROM {C}.information_schema.columns
                        WHERE table_schema = '{S}' AND table_name LIKE 'clean_%'
                        ORDER BY table_name, ordinal_position""")
    schema = {}
    for t, c, d in cols:
        schema.setdefault(t, []).append(f"{c} ({d})")
    return "\n".join(f"{C}.{S}.{t}: " + ", ".join(cs) for t, cs in schema.items())


@lru_cache(maxsize=1)
def sql_system():
    return f"""You write Databricks SQL for a business analyst agent.
Tables:
{schema_text()}
Notes:{data_notes()}
Return ONLY one SELECT query, no explanation, no markdown."""

