# AI Data Team

Ask a business question and get a answer backed by SQL on real tables. A small team of AI agents plans the work, writes the SQL, checks it, and explains the result. It runs on Databricks Free Edition with Databricks-hosted models, so there are no API costs.

## Example

```
python -m src.cli "How did revenue change from 2024 to 2025, and which category drove the change?"
```

> From 2024 to 2025, revenue increased by $37,372.47, a 7.7% change. The Electronics category drove the largest change, with a $21,959.44 increase, 12.8% growth from $171,400.93 to $193,360.37.

## How it works

| Agent | Job |
|---|---|
| **Planner** | Splits the question into 1 to 3 plain-English sub-questions |
| **Analyst** | Writes one SQL query per sub-question and runs it on Databricks |
| **Reviewer** | Checks the SQL against the data rules and sends it back once if wrong |
| **Writer** | Turns the approved results into a short answer for a non-technical client |

Safety: only a single read-only `SELECT` or `WITH` query can run. Anything else is blocked and covered by tests.

## Data

Four sample e-commerce tables (customers, orders, monthly revenue, product summary), loaded into Databricks and cleaned into `clean_*` tables. 25,000 orders from 2020-01-01 to 2026-03-30.

## Stack

Python, SQL, Databricks (Free Edition, SQL warehouse and hosted LLM `databricks-meta-llama-3-3-70b-instruct`), VS Code, GitHub, pytest.

## Website

A black-and-white site (`web/`) served by a FastAPI backend (`src/api/`). It has four pages: an overview, a dashboard (with an INR/USD switch), a chat with the agent team that shows every step and the SQL behind each answer, and a pipeline page with live data-quality checks.

```
uvicorn src.api.main:app --reload     # then open http://localhost:8000
```

### Three ways to run it

| Mode | Data | Model | Needs |
|---|---|---|---|
| **Local test** (default without credentials) | DuckDB over `data/raw` | scripted mock, answers a few question types with real SQL | nothing |
| **Local data, real model** | DuckDB | `LLM_BACKEND=databricks` or `anthropic` | a token or API key |
| **Full Databricks** (default with credentials in `.env`) | Databricks SQL warehouse | Databricks-hosted Llama | Databricks Free Edition |

Copy `.env.example` to `.env` to choose. Local mode builds the same `clean_*` tables as notebook 03 and translates the agents' Databricks SQL to DuckDB with sqlglot, so the agent code is unchanged. The local tables reproduce the ground-truth numbers in `tests/test_live_answers.py`.

### API

| Route | Purpose |
|---|---|
| `GET /api/health` | active backends, suggested questions, questions left today |
| `GET /api/dashboard` | KPIs and chart data from the clean tables |
| `GET /api/quality` | table sizes and the notebook 03 quality checks |
| `POST /api/ask` | streams the agent steps, then the answer, SQL, rows and a chart |

Protection for a public deployment: a per-visitor rate limit, a daily question cap, a question length limit and an answer cache (`.env.example` lists the settings).

### Tests

```
python -m pytest -q                 # local data and mock model, no account needed
RUN_LIVE=1 python -m pytest -q      # adds the live Databricks check
```

## Project layout

```
notebooks/   data upload, table creation, cleaning, agent demos
src/agents/  config, db, llm, guard (SQL safety), prompts, team (the agents)
src/agents/  also: local_db (DuckDB mode), mock_llm, charts
src/api/     FastAPI backend: dashboard, quality checks, streamed answers, limits
web/         the website
src/cli.py   ask a question from the terminal
tests/       unit tests: SQL safety guard, local data, charts, agent team, API
```

## Run it

1. Create a Databricks Free Edition workspace and an access token.
2. Create `.env` with `DATABRICKS_HOST` and `DATABRICKS_TOKEN`.
3. `pip install -r requirements.txt`
4. Run notebooks `01` to `03` to load and clean the data.
5. `python -m src.cli "your question"`

## Challenges and fixes

- **Wrong time window:** "last 12 months" used today's date, but the data ends in March 2026. The agent now anchors relative periods to the latest order date.
- **Wrong revenue column:** the model summed `subtotal_usd` instead of `total_amount_usd`. Fixed with explicit data rules in the prompt.
- **Planner wrote SQL:** it invented table and column names. It now writes plain-English sub-questions only.
- **Half-answered questions:** the planner skipped the overall total. It now asks for both the total and the breakdown.
- **Over-strict reviewer:** it rejected valid SQL for extra columns. It now rejects only wrong period, metric or grouping.
- **Unstable answers on multi-step questions:** "deepest drop per year" gave different answers on every run. Causes: a prompt rule that forced `LIMIT 3`, no worked example, and the analyst not seeing its own rejected SQL on retry. Fixed by adding a worked SQL example, passing the previous SQL back on retry, and giving the reviewer the schema.
- **Writer misplacing decimals:** amounts came out 10x too big. Fixed with an explicit "copy numbers exactly" rule.
- **Model comparison:** tested four hosted models against a plain-SQL ground truth. Llama 3.3 70B and Llama 4 Maverick matched exactly. Qwen3 skipped the per-year breakdown. gpt-oss returned an empty answer.
- **Regression test:** a live test checks the agent's answer against ground-truth numbers (`RUN_LIVE=1 python -m pytest`).

## Data limitations

- The dataset is sample data, not real customers.
- About 74% of orders are dated before the customer's registration date, so the agent is told not to answer tenure or signup-cohort questions.
- Small models can still make mistakes, so each answer shows the SQL used.
