# AI Data Team

Ask a business question and get a plain-English answer backed by SQL on real tables. A small team of AI agents plans the work, writes the SQL, checks it, and explains the result. It runs on Databricks Free Edition with Databricks-hosted models, so there are no API costs.

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

## Project layout

```
notebooks/   data upload, table creation, cleaning, agent demos
src/agents/  config, db, llm, guard (SQL safety), prompts, team (the agents)
src/cli.py   ask a question from the terminal
tests/       unit tests for the SQL safety guard
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

## Data limitations

- The dataset is sample data, not real customers.
- About 74% of orders are dated before the customer's registration date, so the agent is told not to answer tenure or signup-cohort questions.
- Small models can still make mistakes, so each answer shows the SQL used.
