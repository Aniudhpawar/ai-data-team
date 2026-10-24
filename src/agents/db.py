from functools import lru_cache
from databricks.sdk import WorkspaceClient
from . import config  # noqa: F401  (loads .env)


@lru_cache(maxsize=1)
def client():
    return WorkspaceClient()


@lru_cache(maxsize=1)
def _warehouse_id():
    return next(iter(client().warehouses.list())).id


def query(sql):
    """Run SQL on Databricks. Returns (column_names, rows)."""
    r = client().statement_execution.execute_statement(
        statement=sql, warehouse_id=_warehouse_id(), wait_timeout="50s")
    if r.status.state.value != "SUCCEEDED":
        raise RuntimeError(r.status.error.message)
    names = [c.name for c in r.manifest.schema.columns]
    rows = r.result.data_array if r.result and r.result.data_array else []
    return names, rows
