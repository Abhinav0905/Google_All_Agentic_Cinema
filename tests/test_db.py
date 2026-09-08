"""Persistence: runs, findings, fixes, and decisions survive a cache drop."""

from api.db import database_backend, list_decisions, normalize_database_url, record_decision
from api.store import StoredRun, store
from engine.models import Finding, Fix, Run


def test_normalize_replit_postgres_url():
    assert normalize_database_url("postgres://u:p@h/db").startswith("postgresql+psycopg://")
    assert normalize_database_url("postgresql://u:p@h/db").startswith("postgresql+psycopg://")
    assert normalize_database_url("postgresql+psycopg://u:p@h/db").startswith(
        "postgresql+psycopg://"
    )


def test_default_backend_is_sqlite_without_env_postgres():
    assert database_backend("sqlite:///tmp/x.sqlite") == "sqlite"
    assert database_backend("postgresql+psycopg://u:p@h/db") == "postgres"


def test_run_reloads_after_cache_drop():
    run = Run(id="persist-1", profile_id="adult", status="completed")
    run.findings = [
        Finding(
            id="f1",
            code="CPS_HIGH",
            severity="error",
            start_ms=0,
            end_ms=1000,
            message="too fast",
            evidence="21 cps",
            spec_ref="adult.cps",
        )
    ]
    run.fixes = [
        Fix(
            id="x1",
            finding_ids=["f1"],
            type="split",
            auto=True,
            status="proposed",
        )
    ]
    store.put(StoredRun(run=run, caption_ready=True))
    store.drop_cache()

    reloaded = store.get("persist-1")
    assert reloaded.run.status == "completed"
    assert reloaded.run.findings[0].code == "CPS_HIGH"
    assert reloaded.run.fixes[0].id == "x1"
    assert reloaded.caption_ready is True

    listed = store.list()
    assert any(item.run.id == "persist-1" for item in listed)


def test_decision_row_is_recorded():
    run = Run(id="persist-2", profile_id="kids", status="completed")
    run.fixes = [Fix(id="x2", finding_ids=[], type="trim", auto=True, status="proposed")]
    store.put(StoredRun(run=run))
    record_decision("persist-2", "x2", "accept")
    rows = list_decisions("persist-2")
    assert len(rows) == 1
    assert rows[0]["decision"] == "accept"
    assert rows[0]["fix_id"] == "x2"
