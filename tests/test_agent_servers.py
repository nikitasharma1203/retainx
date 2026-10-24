import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from mcp_server import sql_server as srv
from src import config


def _roles_ready():
    if os.getenv("RETAINX_TEST_ROLES") != "1":      # opt-in: these tests create database roles
        return False
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("car", "scripts/create_agent_roles.py")
        mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        mod.main()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(not _roles_ready(), reason="opt-in: set RETAINX_TEST_ROLES=1 (creates read-only roles agent_raw and agent_marts in your database)")


def test_raw_mode_sees_everything_and_handles_odd_sql():
    e = srv.make_engine("raw")
    assert "raw.online_retail" in srv.list_tables(e)
    r = srv.run_sql(e, "select round(sum(quantity*price)::numeric, 2) as s, '12:00'::text as t from raw.online_retail where description like 'ITEM%'")
    assert r["columns"] == ["s", "t"] and r["rows"][0][1] == "12:00"


def test_only_single_select_is_allowed():
    e = srv.make_engine("raw")
    for bad in ["drop table analytics.fct_orders", "select 1; select 2", "update analytics.fct_orders set n_lines = 0"]:
        with pytest.raises(ValueError):
            srv.run_sql(e, bad)


def test_writes_fail_even_when_disguised_as_select():
    e = srv.make_engine("raw")
    with pytest.raises(DBAPIError):
        srv.run_sql(e, "with d as (delete from analytics.fct_orders returning 1) select count(*) from d")


def test_documented_mode_cannot_see_raw_data():
    e = srv.make_engine("documented")
    assert not any(t.startswith("raw.") for t in srv.list_tables(e))
    with pytest.raises(DBAPIError):
        srv.run_sql(e, "select * from raw.online_retail limit 1")
    docs = {d["table"]: d for d in srv.describe_data(e)}
    assert "analytics.fct_orders" in docs and docs["analytics.fct_orders"]["columns"]["order_revenue"]["meaning"]
    assert "analytics.stg_transactions" not in docs
