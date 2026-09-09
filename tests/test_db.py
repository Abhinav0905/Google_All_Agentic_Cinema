"""Persistence: runs, findings, fixes, and decisions survive a cache drop."""

import time
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import text

from api import db as dbmod
from api.db import (
    apply_decisions_to_run,
    database_backend,
    dispose_engine,
    list_decisions,
    normalize_database_url,
    record_decision,
    reset_engine,
)
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


def test_hosted_pool_recovers_when_an_idle_connection_is_closed(tmp_path, monkeypatch):
    """Use production pool options with a local DB to simulate an idle disconnect."""
    create_engine = dbmod.create_engine

    def local_database(url, **options):
        # No Postgres service or network is needed to exercise pool checkout.
        assert url == "postgresql+psycopg://unused/local-test"
        return create_engine(f"sqlite:///{tmp_path / 'pool.sqlite'}", **options)

    monkeypatch.setattr(dbmod, "create_engine", local_database)
    engine = dbmod._create_engine("postgresql+psycopg://unused/local-test")
    try:
        with engine.begin() as connection:
            connection.execute(text("create table marker (value integer)"))
            connection.execute(text("insert into marker values (42)"))
            idle_connection = connection.connection.driver_connection

        # The connection is already back in the pool when the server closes it.
        idle_connection.close()

        with engine.connect() as connection:
            assert connection.scalar(text("select value from marker")) == 42
            assert connection.connection.driver_connection is not idle_connection
    finally:
        engine.dispose()


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


def test_dispose_engine_releases_and_can_reinit():
    reset_engine("sqlite://")
    assert dbmod._engine is not None
    dispose_engine()
    assert dbmod._engine is None
    assert dbmod._Session is None
    reset_engine("sqlite://")
    assert dbmod._engine is not None


def test_pipeline_overwrite_keeps_recorded_decision():
    """A fresh pipeline Run must not wipe an accept recorded during the run."""
    running = Run(id="race-1", profile_id="adult", status="running")
    running.fixes = [Fix(id="x1", finding_ids=[], type="split", auto=True, status="accepted")]
    stored = store.put(StoredRun(run=running))
    record_decision("race-1", "x1", "accept")

    fresh = Run(id="race-1", profile_id="adult", status="completed")
    fresh.fixes = [Fix(id="x1", finding_ids=[], type="split", auto=True, status="proposed")]

    class _Pctx:
        run = fresh
        cues = []
        ad_cues = []
        segments = []
        audio_events = []
        visual_events = []

    store.apply_pipeline_result(stored, _Pctx())
    assert store.get("race-1").run.fixes[0].status == "accepted"

    store.drop_cache()
    reloaded = store.get("race-1")
    assert reloaded.run.fixes[0].status == "accepted"
    apply_decisions_to_run(fresh)
    assert fresh.fixes[0].status == "accepted"


def test_decision_row_is_recorded():
    run = Run(id="persist-2", profile_id="kids", status="completed")
    run.fixes = [Fix(id="x2", finding_ids=[], type="trim", auto=True, status="proposed")]
    store.put(StoredRun(run=run))
    record_decision("persist-2", "x2", "accept")
    rows = list_decisions("persist-2")
    assert len(rows) == 1
    assert rows[0]["decision"] == "accept"
    assert rows[0]["fix_id"] == "x2"


def test_owner_and_upload_sizes_survive_database_reload():
    stored = StoredRun(
        run=Run(id="owned-1", profile_id="adult", analysis_mode="caption_only"),
        owner_id="one-way-session-digest",
        upload_sizes={"video": 4321},
    )
    store.put(stored)
    store.drop_cache()
    restored = store.get("owned-1")
    assert restored.owner_id == "one-way-session-digest"
    assert restored.upload_sizes == {"video": 4321}
    assert restored.run.analysis_mode == "caption_only"


def test_legacy_payload_remains_unclaimed():
    legacy = {"run": Run(id="legacy-1", profile_id="adult").model_dump()}
    restored = dbmod.hydrate_stored(legacy, StoredRun)
    assert restored.owner_id == ""
    assert restored.upload_sizes == {}


def test_inline_media_survives_actual_database_reopen(tmp_path):
    url = f"sqlite:///{tmp_path / 'durable.sqlite'}"
    reset_engine(url)
    dbmod.save_asset("run-1", "video", b"video-bytes")
    dispose_engine()
    reset_engine(url)
    assert dbmod.load_asset("run-1", "video") == b"video-bytes"
    reset_engine("sqlite://")


def test_concurrent_reads_share_one_hydrated_run(monkeypatch):
    import importlib

    store_module = importlib.import_module("api.store")
    store.put(StoredRun(run=Run(id="shared-1", profile_id="adult")))
    store.drop_cache()
    load = store_module.load_payload

    def delayed_load(run_id):
        payload = load(run_id)
        time.sleep(0.01)
        return payload

    monkeypatch.setattr(store_module, "load_payload", delayed_load)
    with ThreadPoolExecutor(max_workers=4) as pool:
        items = list(pool.map(store.get, ["shared-1"] * 4))
    assert all(item is items[0] for item in items)


def test_repeated_live_observation_ids_do_not_abort_persistence():
    """Regression: live AD cue 2 overlapped two separate dialogue segments."""
    run = Run(id="live-ad-overlap", profile_id="adult", status="completed", analysis_mode="live")
    run.findings = [
        Finding(
            id="AD_OVERLAPS_DIALOGUE_2_5200",
            code="AD_OVERLAPS_DIALOGUE",
            severity="error",
            cue_index=2,
            start_ms=5200,
            end_ms=6800,
            message=f"AD cue overlaps dialogue by {duration}ms",
            evidence=evidence,
            spec_ref="Project AD overlap tolerance",
        )
        for duration, evidence in ((270, "segment 2500-5470"), (630, "segment 6170-7880"))
    ]
    run.fixes = [
        Fix(
            id="FIX_AD_OVERLAPS_DIALOGUE_2_5200",
            finding_ids=["AD_OVERLAPS_DIALOGUE_2_5200"],
            type="retime_ad",
            auto=True,
        )
        for _ in range(2)
    ]
    stored = StoredRun(run=run, owner_id="session-digest")
    store.put(stored)
    store.save(stored)
    store.drop_cache()
    restored = store.get(run.id)
    assert restored.run.status == "completed"
    assert len(restored.run.findings) == 2
    assert len(restored.run.fixes) == 2
    assert restored.run.findings[0].evidence != restored.run.findings[1].evidence
    with dbmod.get_session() as session:
        findings = session.query(dbmod.QcFinding).filter_by(run_id=run.id).all()
        fixes = session.query(dbmod.QcFix).filter_by(run_id=run.id).all()
        assert len(findings) == 2
        assert len(fixes) == 2
