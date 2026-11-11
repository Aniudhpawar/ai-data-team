"""Run the tests on local data and the mock model, so they need no account and cost nothing.
The live test (RUN_LIVE=1) keeps whatever backend your .env selects."""
import os

if os.getenv("RUN_LIVE") != "1":
    os.environ["DATA_BACKEND"] = "local"
    os.environ["LLM_BACKEND"] = "mock"
