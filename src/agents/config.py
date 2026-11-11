import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(override=True)

MODEL = os.getenv("LLM_ENDPOINT", "databricks-meta-llama-3-3-70b-instruct")
CATALOG = "workspace"
SCHEMA = "ai_data_team"

# Where the data lives and which model answers. With Databricks credentials in .env
# both default to Databricks (the original setup). Without them the project runs fully
# on your laptop: DuckDB over the CSVs in data/raw and a scripted mock model.
#   DATA_BACKEND = databricks | local
#   LLM_BACKEND  = databricks | anthropic | mock
_has_databricks = bool(os.getenv("DATABRICKS_HOST") and os.getenv("DATABRICKS_TOKEN"))
DATA_BACKEND = os.getenv("DATA_BACKEND", "databricks" if _has_databricks else "local").lower()
LLM_BACKEND = os.getenv("LLM_BACKEND", "databricks" if _has_databricks else "mock").lower()

ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
DATA_DIR = Path(os.getenv("DATA_DIR", Path(__file__).resolve().parents[2] / "data" / "raw"))
