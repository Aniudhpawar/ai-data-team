"""Live test against Databricks. Run with: RUN_LIVE=1 python -m pytest -q"""
import os
import pytest

pytestmark = pytest.mark.skipif(os.getenv("RUN_LIVE") != "1", reason="set RUN_LIVE=1 to run")


def test_deepest_monthly_drop_per_year():
    from src.agents.team import team
    answer = team("Which month had the deepest month-over-month drop in sales "
                  "in each year from 2020 to 2026?")
    for amount in ["7,242.91", "9,686.74", "10,611.13", "7,555.81",
                   "5,669.75", "10,772.66", "5,791.15"]:
        assert amount in answer, f"missing {amount}"
