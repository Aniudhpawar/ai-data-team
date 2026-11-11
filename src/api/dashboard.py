"""Numbers for the website, read from the same clean_* tables the agents use,
so a chart and an agent's answer always agree."""
import threading
import time

from src.agents.config import CATALOG as C, SCHEMA as S
from src.agents.db import query

T = f"{C}.{S}"
_cache, _lock = {}, threading.Lock()
TTL = 600  # seconds


def cached(key, fn):
    with _lock:
        hit = _cache.get(key)
        if hit and time.time() - hit[0] < TTL:
            return hit[1]
    value = fn()
    with _lock:
        _cache[key] = (time.time(), value)
    return value


def _rows(sql):
    return query(sql)[1]


def _f(x):
    return float(x) if x is not None else 0.0


def dashboard():
    def build():
        total, orders, customers, aov, ret = _rows(f"""
            SELECT SUM(total_amount_usd), COUNT(*), COUNT(DISTINCT customer_id),
                   AVG(total_amount_usd), AVG(returned) FROM {T}.clean_orders""")[0]
        last12, prev12 = _rows(f"""
            WITH o AS (SELECT year * 12 + month AS ym, total_amount_usd AS t FROM {T}.clean_orders),
                 mx AS (SELECT MAX(ym) AS m FROM o)
            SELECT SUM(CASE WHEN ym > m - 12 THEN t END),
                   SUM(CASE WHEN ym > m - 24 AND ym <= m - 12 THEN t END) FROM o, mx""")[0]
        first, last = _rows(f"SELECT MIN(order_date), MAX(order_date) FROM {T}.clean_orders")[0]
        monthly = [[int(y), int(m), _f(v)] for y, m, v in _rows(f"""
            SELECT year, month, SUM(total_amount_usd) FROM {T}.clean_orders
            GROUP BY year, month ORDER BY year, month""")]
        yearly = [[int(y), _f(v)] for y, v in _rows(f"""
            SELECT year, SUM(total_amount_usd) FROM {T}.clean_orders GROUP BY year ORDER BY year""")]

        def ranked(sql):
            return [[k, _f(v)] for k, v in _rows(sql)]

        return {
            "range": {"from": first, "to": last},
            "kpis": {"revenue": _f(total), "orders": int(_f(orders)), "customers": int(_f(customers)),
                     "avg_order_value": _f(aov), "return_rate": _f(ret),
                     "last_12_months": _f(last12), "previous_12_months": _f(prev12)},
            "monthly": monthly,
            "yearly": yearly,
            "categories": ranked(f"""SELECT category, SUM(total_amount_usd) AS v FROM {T}.clean_orders
                                     GROUP BY category ORDER BY v DESC LIMIT 8"""),
            "products": ranked(f"""SELECT product_name, SUM(total_amount_usd) AS v FROM {T}.clean_orders
                                   GROUP BY product_name ORDER BY v DESC LIMIT 8"""),
            "tiers": ranked(f"""SELECT c.membership_tier, SUM(o.total_amount_usd) AS v
                                FROM {T}.clean_orders o JOIN {T}.clean_customers c USING (customer_id)
                                GROUP BY c.membership_tier ORDER BY v DESC"""),
            "channels": ranked(f"""SELECT c.acquisition_channel, SUM(o.total_amount_usd) AS v
                                   FROM {T}.clean_orders o JOIN {T}.clean_customers c USING (customer_id)
                                   GROUP BY c.acquisition_channel ORDER BY v DESC"""),
        }
    return cached("dashboard", build)


def quality():
    """The data-quality report from notebooks/03_clean_data.ipynb, plus table sizes."""
    def build():
        def one(sql):
            return _rows(sql)[0][0]

        def n(table):
            return int(one(f"SELECT COUNT(*) FROM {T}.{table}"))

        raw_c, clean_c, raw_o, clean_o = n("customers"), n("clean_customers"), n("orders"), n("clean_orders")
        unknown = int(one(f"""SELECT COUNT(*) FROM {T}.clean_orders o
                              LEFT JOIN {T}.clean_customers c USING (customer_id) WHERE c.customer_id IS NULL"""))
        early = int(one(f"""SELECT COUNT(*) FROM {T}.clean_orders o JOIN {T}.clean_customers c USING (customer_id)
                            WHERE o.order_date < c.registration_date"""))
        mismatch = int(one(f"""SELECT COUNT(*) FROM {T}.clean_orders WHERE ABS(total_amount_usd -
                               (subtotal_usd - discount_amount_usd + shipping_fee_usd + tax_amount_usd)) > 0.05"""))
        null_total = int(one(f"SELECT COUNT(*) FROM {T}.clean_orders WHERE total_amount_usd IS NULL"))
        first, last = _rows(f"SELECT MIN(order_date), MAX(order_date) FROM {T}.clean_orders")[0]
        pct_early = round(100 * early / clean_o, 1) if clean_o else 0

        def status(ok):
            return "pass" if ok else "warn"

        checks = [
            {"check": "Customers: raw rows to clean rows", "table": "clean_customers",
             "result": f"{raw_c:,} to {clean_c:,}", "status": "pass" if raw_c == clean_c else "info"},
            {"check": "Orders: raw rows to clean rows", "table": "clean_orders",
             "result": f"{raw_o:,} to {clean_o:,}", "status": "pass" if raw_o == clean_o else "info"},
            {"check": "Orders with an unknown customer", "table": "clean_orders",
             "result": f"{unknown:,}", "status": status(unknown == 0)},
            {"check": "Orders with a missing total", "table": "clean_orders",
             "result": f"{null_total:,}", "status": status(null_total == 0)},
            {"check": "Total equals subtotal minus discount plus shipping plus tax", "table": "clean_orders",
             "result": f"{mismatch:,} mismatches", "status": status(mismatch == 0)},
            {"check": "Orders dated before the customer registered", "table": "clean_orders",
             "result": f"{early:,} ({pct_early}%), known quirk of the sample data", "status": "warn" if early else "pass"},
            {"check": "Order date range", "table": "clean_orders",
             "result": f"{first} to {last}", "status": "info"},
        ]
        tables = [{"table": t, "rows": n(t), "layer": "clean" if t.startswith("clean_") else "raw"}
                  for t in ["customers", "orders", "monthly_revenue", "product_summary",
                            "clean_customers", "clean_orders", "clean_monthly_revenue", "clean_product_summary"]]
        return {"checks": checks, "tables": tables}
    return cached("quality", build)
