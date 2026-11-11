"""The whole agent team on local data with the mock model, checked against the ground truth
that tests/test_live_answers.py uses for Databricks."""
from src.agents.team import run_team


def test_deepest_monthly_drop_per_year_matches_ground_truth():
    r = run_team("Which month had the deepest month-over-month drop in sales in each year from 2020 to 2026?")
    for amount in ["7242.91", "9686.74", "10611.13", "7555.81", "5669.75", "10772.66", "5791.15"]:
        assert amount in r["answer"], amount


def test_revenue_change_example_from_readme():
    r = run_team("How did revenue change from 2024 to 2025, and which category drove the change?")
    assert len(r["subquestions"]) == 2
    assert "37372.47" in r["answer"] and "21959.44" in r["answer"]


def test_events_are_emitted_in_order():
    seen = []
    run_team("What are the top 5 products by revenue?", emit=lambda e: seen.append(e["type"]))
    assert seen == ["question", "plan", "analyst", "review", "writing"]
