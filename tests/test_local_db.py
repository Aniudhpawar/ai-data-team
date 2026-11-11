from src.agents.local_db import query

T = "workspace.ai_data_team"


def test_row_counts_match_the_databricks_tables():
    assert query(f"SELECT COUNT(*) FROM {T}.clean_orders")[1][0][0] == "25000"
    assert query(f"SELECT COUNT(*) FROM {T}.clean_customers")[1][0][0] == "8000"


def test_date_range_matches_readme():
    lo, hi = query(f"SELECT MIN(order_date), MAX(order_date) FROM {T}.clean_orders")[1][0]
    assert (lo, hi) == ("2020-01-01", "2026-03-30")


def test_databricks_date_function_is_translated():
    rows = query(f"SELECT COUNT(*) FROM {T}.clean_orders WHERE order_date > DATE_ADD('2026-03-30', -365)")[1]
    assert int(rows[0][0]) > 0


def test_schema_lookup_works():
    from src.agents.prompts import schema_text
    text = schema_text()
    assert "clean_orders" in text and "total_amount_usd" in text
