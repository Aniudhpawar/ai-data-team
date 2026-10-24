import os
from dotenv import load_dotenv

load_dotenv(override=True)

MODEL = os.getenv("LLM_ENDPOINT", "databricks-meta-llama-3-3-70b-instruct")
CATALOG = "workspace"
SCHEMA = "ai_data_team"
