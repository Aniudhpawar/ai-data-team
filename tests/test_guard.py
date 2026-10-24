import pytest
from src.agents.guard import clean_sql


def test_allows_select():
    assert clean_sql("SELECT 1") == "SELECT 1"


def test_strips_markdown_and_semicolon():
    assert clean_sql("```sql\nSELECT 1;\n```") == "SELECT 1"


def test_allows_cte():
    assert clean_sql("WITH a AS (SELECT 1) SELECT * FROM a").startswith("WITH")


@pytest.mark.parametrize("bad", [
    "DROP TABLE x",
    "SELECT 1; DROP TABLE x",
    "DELETE FROM x",
    "SELECT * FROM x WHERE 1=1; UPDATE x SET a=1",
    "hello",
])
def test_blocks_unsafe(bad):
    with pytest.raises(ValueError):
        clean_sql(bad)
