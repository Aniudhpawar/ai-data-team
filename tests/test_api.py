import json

from fastapi.testclient import TestClient

from src.api import main
from src.api.limits import AnswerCache, DailyCap, RateLimiter

client = TestClient(main.app)


def _events(resp):
    return [json.loads(line) for line in resp.text.strip().split("\n")]


def test_health_reports_backends():
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["llm_backend"] == "mock" and h["suggested"]


def test_dashboard_numbers():
    d = client.get("/api/dashboard").json()
    assert d["kpis"]["orders"] == 25000
    assert len(d["monthly"]) == 75
    assert d["range"]["to"] == "2026-03-30"


def test_quality_checks_present():
    q = client.get("/api/quality").json()
    assert any("unknown customer" in c["check"] for c in q["checks"])


def test_ask_streams_steps_then_result():
    main.limiter = RateLimiter(100)
    ev = _events(client.post("/api/ask", json={"question": "What are the top 5 products by revenue?"}))
    assert [e["type"] for e in ev][:2] == ["question", "plan"]
    assert ev[-1]["type"] == "result" and ev[-1]["chart"]["kind"] == "bar"


def test_ask_validation():
    main.limiter = RateLimiter(100)
    assert client.post("/api/ask", json={"question": "   "}).status_code == 400
    assert client.post("/api/ask", json={"question": "x" * 1000}).status_code == 400


def test_rate_limit_blocks_the_sixth_question():
    main.limiter = RateLimiter(5)
    codes = [client.post("/api/ask", json={"question": "top products by revenue"}).status_code for _ in range(6)]
    assert codes[:5] == [200] * 5 and codes[5] == 429


def test_daily_cap_and_cache_units():
    cap = DailyCap(2)
    assert cap.take() and cap.take() and not cap.take()
    c = AnswerCache()
    c.put("Top products?", {"a": 1})
    assert c.get("top products") == {"a": 1}
