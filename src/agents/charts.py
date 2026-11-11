"""Turn an agent finding (columns + rows of text) into a small chart description for the website."""
import re

PREFER_DELTA = re.compile(r"diff|change|delta|growth", re.I)
PREFER_VALUE = re.compile(r"revenue|total|amount|spend|sales|orders|count|units|rate|pct", re.I)
TIME_COLS = ("year", "month")
MAX_POINTS = 24


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _is_numeric(rows, i):
    vals = [r[i] for r in rows if r[i] is not None]
    return bool(vals) and all(_num(v) is not None for v in vals)


def unit_for(name):
    n = name.lower()
    if re.search(r"pct|percent|rate|share", n):
        return "pct"
    if re.search(r"count|orders|units|quantity|customers|number", n):
        return "count"
    return "usd"


def chart_for(finding):
    """Return {kind, title, labels, values, unit} or None when the result is not chartable."""
    cols, rows = finding["columns"], finding["rows"]
    if len(rows) < 2 or len(cols) < 2:
        return None
    lower = [c.lower() for c in cols]
    numeric = [i for i in range(len(cols)) if _is_numeric(rows, i)]

    time_idx = [lower.index(t) for t in TIME_COLS if t in lower]
    label_idx = [i for i in range(len(cols)) if i not in numeric]
    value_pool = [i for i in numeric if i not in time_idx]
    if not value_pool:
        return None

    def pick_value():
        for rx in (PREFER_DELTA, PREFER_VALUE):
            hit = [i for i in value_pool if rx.search(cols[i])]
            if hit:
                return hit[0]
        return value_pool[0]

    v = pick_value()
    if time_idx and len(time_idx) == 2:
        y, m = lower.index("year"), lower.index("month")
        labels = [f"{r[y]}-{int(float(r[m])):02d}" for r in rows]
        kind = "line" if len(rows) > 12 else "bar"  # a few months or years read better as bars
    elif time_idx and "year" in lower:
        labels = [str(r[lower.index("year")]) for r in rows]
        kind = "line" if len(rows) >= 4 else "bar"
    elif label_idx:
        labels = [str(r[label_idx[0]]) for r in rows]
        kind = "bar"
    else:
        return None
    values = [_num(r[v]) for r in rows]
    if any(x is None for x in values):
        return None
    labels, values = labels[-MAX_POINTS:], values[-MAX_POINTS:]
    # The sub-question describes the chart better than a column name does
    title = (finding.get("question") or cols[v].replace("_", " ")).strip()
    return {"kind": kind, "title": title, "metric": cols[v].replace("_", " "),
            "labels": labels, "values": values, "unit": unit_for(cols[v])}


def best_chart(findings):
    for f in findings:
        c = chart_for(f)
        if c:
            return c
    return None
