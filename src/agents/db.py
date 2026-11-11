from functools import lru_cache
from . import config


@lru_cache(maxsize=1)
def client():
    from databricks.sdk import WorkspaceClient
    return WorkspaceClient()


@lru_cache(maxsize=1)
def _warehouse_id():
    return next(iter(client().warehouses.list())).id


def query(sql):
    """Run SQL. Returns (column_names, rows). Databricks by default, DuckDB when DATA_BACKEND=local."""
    if config.DATA_BACKEND == "local":
        from . import local_db
        return local_db.query(sql)
    r = client().statement_execution.execute_statement(
        statement=sql, warehouse_id=_warehouse_id(), wait_timeout="50s")
    if r.status.state.value != "SUCCEEDED":
        raise RuntimeError(r.status.error.message)
    names = [c.name for c in r.manifest.schema.columns]
    rows = r.result.data_array if r.result and r.result.data_array else []
    return names, rows
