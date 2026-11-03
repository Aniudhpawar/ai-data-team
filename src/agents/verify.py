import json
import re
from itertools import combinations
from .llm import llm

MONEY = re.compile(r"\$\s?([\d,]+(?:\.\d+)?)")


def _numbers(obj, out):
    if isinstance(obj, (list, tuple)):
        for x in obj:
            _numbers(x, out)
    elif isinstance(obj, dict):
        for x in obj.values():
            _numbers(x, out)
    else:
        try:
            out.add(abs(float(str(obj).replace(",", ""))))
        except ValueError:
            pass


def check_numbers(answer, findings):
    """Return dollar amounts in the answer that are not in the findings."""
    base = set()
    _numbers([f["rows"] for f in findings], base)
    allowed = set(base)
    for a, b in combinations(base, 2):   # writer may state differences or sums
        allowed.add(abs(a - b))
        allowed.add(a + b)
    bad = []
    for m in MONEY.findall(answer):
        v = float(m.replace(",", ""))
        if not any(abs(v - a) <= max(0.51, a * 1e-4) for a in allowed):
            bad.append("$" + m)
    return bad


def check_answer(question, findings, answer):
    return llm(
        "You check a data team's final answer before it goes to a client. Compare it with the "
        "client's question and the findings. Reply FIX only if: (1) it does not answer the "
        "question asked, (2) it claims a time period, month or grouping that the findings do "
        "not show, (3) it ties together numbers from separate findings as if they were "
        "connected, or (4) it states something the findings do not support, or (5) it mentions a data limitation or missing information that the client did not ask about or that the findings contradict. Wording, "
        "rounding and formatting are NOT reasons to reject. "
        "Reply with exactly 'OK' or 'FIX: <one sentence>'.",
        f"Client question: {question}\nFindings: {json.dumps(findings, default=str)}\n"
        f"Answer: {answer}", max_tokens=100).strip()


def verify(question, findings, answer):
    problems = []
    bad = check_numbers(answer, findings)
    if bad:
        problems.append("These dollar amounts are not in the findings: "
                        f"{', '.join(bad)}. Use only amounts from the findings.")
    verdict = check_answer(question, findings, answer)
    if not verdict.upper().startswith("OK"):
        problems.append(verdict)
    return problems