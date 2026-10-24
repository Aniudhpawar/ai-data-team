from src.agents.db import query

SQL = """
WITH m AS (
  SELECT year, month, SUM(total_amount_usd) AS revenue
  FROM workspace.ai_data_team.clean_orders GROUP BY year, month
), d AS (
  SELECT year, month, revenue,
         revenue - LAG(revenue) OVER (ORDER BY year, month) AS change
  FROM m
), r AS (
  SELECT *, ROW_NUMBER() OVER (PARTITION BY year ORDER BY change ASC) AS rn
  FROM d WHERE change < 0
)
SELECT year, month, ROUND(revenue, 2) AS revenue, ROUND(change, 2) AS change
FROM r WHERE rn = 1 ORDER BY year
"""
names, rows = query(SQL)
print(names)
for row in rows:
    print(row)
