"""Unit tests for worker runtime dependency lifecycle helpers."""

from contextlib import contextmanager
import sys
import types

import apps.worker.main as worker_main


def test_load_runtime_dependencies__loads_storage_and_db_factory(monkeypatch):
    """Runtime dependency loader should wire storage and DB factory."""
    fake_storage = object()

    def fake_storage_factory():
        return fake_storage

    @contextmanager
    def fake_get_db():
        yield object()

    monkeypatch.setitem(
        sys.modules,
        "storage",
        types.SimpleNamespace(create_storage_from_env=fake_storage_factory),
    )
    monkeypatch.setitem(
        sys.modules,
        "database",
        types.SimpleNamespace(get_db=fake_get_db),
    )

    deps = worker_main._load_runtime_dependencies()

    assert deps.storage is fake_storage
    assert deps.get_db is fake_get_db


def test_validate_runtime_dependencies__runs_db_ping():
    """Dependency validator should execute a simple DB liveness query."""
    executed = []

    class FakeDB:
        def execute(self, query):
            executed.append(query)

    @contextmanager
    def fake_get_db():
        yield FakeDB()

    deps = worker_main.WorkerRuntimeDependencies(storage=object(), get_db=fake_get_db)
    worker_main._validate_runtime_dependencies(deps)

    assert executed == ["SELECT 1"]


def test_create_pdf_ingest_activity__returns_fresh_instance(monkeypatch):
    """Each invocation should get a dedicated activity instance."""
    created = []

    class FakePDFActivity:
        def __init__(self, storage, db):
            self.storage = storage
            self.db = db
            created.append(self)

    monkeypatch.setattr(worker_main, "PDFIngestActivity", FakePDFActivity)

    deps = worker_main.WorkerRuntimeDependencies(storage=object(), get_db=lambda: None)
    db_one = object()
    db_two = object()

    activity_one = worker_main._create_pdf_ingest_activity(deps, db_one)
    activity_two = worker_main._create_pdf_ingest_activity(deps, db_two)

    assert activity_one is not activity_two
    assert activity_one.storage is deps.storage
    assert activity_two.storage is deps.storage
    assert activity_one.db is db_one
    assert activity_two.db is db_two
    assert len(created) == 2


def test_create_repo_ingest_activity__returns_fresh_instance(monkeypatch):
    """Each invocation should get a dedicated repo activity instance."""
    created = []

    class FakeRepoActivity:
        def __init__(self, storage, db):
            self.storage = storage
            self.db = db
            created.append(self)

    monkeypatch.setattr(worker_main, "RepoIngestActivity", FakeRepoActivity)

    deps = worker_main.WorkerRuntimeDependencies(storage=object(), get_db=lambda: None)
    db_one = object()
    db_two = object()

    activity_one = worker_main._create_repo_ingest_activity(deps, db_one)
    activity_two = worker_main._create_repo_ingest_activity(deps, db_two)

    assert activity_one is not activity_two
    assert activity_one.storage is deps.storage
    assert activity_two.storage is deps.storage
    assert activity_one.db is db_one
    assert activity_two.db is db_two
    assert len(created) == 2


def test_create_sandbox_run_activity__returns_fresh_instance(monkeypatch):
    """Each invocation should get a dedicated sandbox activity instance."""
    created = []

    class FakeSandboxActivity:
        def __init__(self, storage, db):
            self.storage = storage
            self.db = db
            created.append(self)

    monkeypatch.setattr(worker_main, "SandboxRunActivity", FakeSandboxActivity)

    deps = worker_main.WorkerRuntimeDependencies(storage=object(), get_db=lambda: None)
    db_one = object()
    db_two = object()

    activity_one = worker_main._create_sandbox_run_activity(deps, db_one)
    activity_two = worker_main._create_sandbox_run_activity(deps, db_two)

    assert activity_one is not activity_two
    assert activity_one.storage is deps.storage
    assert activity_two.storage is deps.storage
    assert activity_one.db is db_one
    assert activity_two.db is db_two
    assert len(created) == 2


def test_build_registered_activities__includes_wrappers_and_phase_bundle(monkeypatch):
    """Worker should register wrapper-backed and phase bundle activities together."""
    fake_phase_activity = object()
    monkeypatch.setitem(
        sys.modules,
        "phase_activities",
        types.SimpleNamespace(PHASE_ACTIVITIES=[fake_phase_activity]),
    )

    deps = worker_main.WorkerRuntimeDependencies(storage=object(), get_db=lambda: None)
    activities = worker_main._build_registered_activities(deps)

    wrapper_names = {getattr(fn, "__name__", "") for fn in activities if callable(fn)}
    assert "pdf_ingest_wrapper" in wrapper_names
    assert "repo_ingest_wrapper" in wrapper_names
    assert "sandbox_run_wrapper" in wrapper_names
    assert fake_phase_activity in activities
