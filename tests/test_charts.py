from src.agents.charts import best_chart, chart_for


def test_category_comparison_charts_the_difference():
    c = chart_for({"columns": ["category", "revenue_2024", "revenue_2025", "difference"],
                   "rows": [["A", "1", "2", "1"], ["B", "3", "5", "2"]]})
    assert c["kind"] == "bar" and c["values"] == [1.0, 2.0] and c["title"] == "difference"


def test_a_long_monthly_series_becomes_a_line():
    rows = [["2020", str(m), str(10 + m)] for m in range(1, 13)] + [["2021", "1", "30"]]
    c = chart_for({"columns": ["year", "month", "revenue"], "rows": rows})
    assert c["kind"] == "line" and c["labels"][0] == "2020-01"


def test_single_value_is_not_charted():
    assert chart_for({"columns": ["total"], "rows": [["5"]]}) is None
    assert best_chart([]) is None


def test_a_few_months_are_bars_and_the_title_comes_from_the_question():
    c = chart_for({"question": "Deepest drop in each year",
                   "columns": ["year", "month", "change"],
                   "rows": [["2020", "6", "-7"], ["2021", "4", "-9"], ["2022", "2", "-10"]]})
    assert c["kind"] == "bar" and c["title"] == "Deepest drop in each year" and c["metric"] == "change"
