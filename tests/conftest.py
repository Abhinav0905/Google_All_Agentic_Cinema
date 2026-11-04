"""Force an in-memory SQLite engine so tests never touch the local file DB."""

import os

import pytest

os.environ["DATABASE_URL"] = "sqlite://"

from api.db import reset_engine  # noqa: E402
from api.store import store  # noqa: E402

reset_engine("sqlite://")


@pytest.fixture(autouse=True)
def _isolate_store():
    reset_engine("sqlite://")
    store.clear()
    yield
    store.clear()
