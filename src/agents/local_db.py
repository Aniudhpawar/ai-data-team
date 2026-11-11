"""Local stand-in for the Databricks SQL warehouse.

Loads the CSVs in data/raw into an in-memory DuckDB database, builds the same
clean_* tables that notebooks/03_clean_data.ipynb builds on Databricks, and runs
the agents' Databricks-style SQL by translating it to DuckDB with sqlglot.

Table names match Databricks (workspace.ai_data_team.clean_orders), so the prompts,
the guard and the agents do not change.
"""
import threading
from decimal import Decimal

import duckdb
import sqlglot

from .config import CATALOG as C, DATA_DIR, SCHEMA as S

RAW_TABLES = ["customers", "orders", "monthly_revenue", "product_summary"]

_lock = threading.Lock()
_con = None


def _build():
    con = duckdb.connect()
    con.execute(f"ATTACH ':memory:' AS {C}")
    con.execute(f"CREATE SCHEMA {C}.{S}")
    missing = [t for t in RAW_TABLES if not (DATA_DIR / f"{t}.csv").exists()]
    if missing:
        raise FileNotFoundError(f"Missing CSV files in {DATA_DIR}: {', '.join(missing)}")
    for t in RAW_TABLES:
        con.execute(f"CREATE TABLE {C}.{S}.{t} AS "
                    f"SELECT * FROM read_csv('{(DATA_DIR / (t + '.csv')).as_posix()}', header=true)")

    # Same cleaning as notebooks/03_clean_data.ipynb
    con.execute(f"""CREATE TABLE {C}.{S}.clean_customers AS
        SELECT * EXCLUDE (registration_date),
               CAST(registration_date AS DATE) AS registration_date
        FROM {C}.{S}.customers
        WHERE customer_id IS NOT NULL
        QUALIFY ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY registration_date) = 1""")
    con.execute(f"""CREATE TABLE {C}.{S}.clean_orders AS
        SELECT * EXCLUDE (order_date, delivery_date),
               CAST(order_date AS DATE) AS order_date,
               CAST(delivery_date AS DATE) AS delivery_date
        FROM {C}.{S}.orders
        WHERE order_id IS NOT NULL
        QUALIFY ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY order_date) = 1""")
    con.execute(f"CREATE TABLE {C}.{S}.clean_monthly_revenue AS SELECT * FROM {C}.{S}.monthly_revenue")
    con.execute(f"CREATE TABLE {C}.{S}.clean_product_summary AS SELECT * FROM {C}.{S}.product_summary")
    return con


def connection():
    global _con
    with _lock:
        if _con is None:
            _con = _build()
        return _con


def _text(v):
    """Databricks returns every value as text. Do the same so the agents see identical rows."""
    if v is None:
        return None
    if isinstance(v, (float, Decimal)):
        return format(round(float(v), 6), "f").rstrip("0").rstrip(".") or "0"
    return str(v)


def query(sql):
    """Run Databricks-style SQL locally. Returns (column_names, rows) like db.query."""
    con = connection()
    sql = sql.replace(f"{C}.information_schema.columns", "information_schema.columns")
    try:
        sql = sqlglot.transpile(sql, read="databricks", write="duckdb")[0]
    except Exception:
        pass  # let DuckDB report the real error
    with _lock:
        cur = con.execute(sql)
        names = [d[0] for d in cur.description]
        rows = [[_text(v) for v in r] for r in cur.fetchall()]
    return names, rows
