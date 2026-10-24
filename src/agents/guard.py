import re

FORBIDDEN = re.compile(
    r"\b(insert|update|delete|drop|create|alter|merge|truncate|grant|revoke)\b", re.I)


def clean_sql(text):
    """Strip markdown fences and allow only a single read-only SELECT/WITH query."""
    sql = re.sub(r"^```(?:sql)?|```$", "", text.strip(), flags=re.M).strip().rstrip(";")
    if not re.match(r"^(select|with)\b", sql, re.I) or FORBIDDEN.search(sql) or ";" in sql:
        raise ValueError(f"Blocked unsafe or invalid SQL:\n{sql}")
    return sql
