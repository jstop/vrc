"""Shared fixtures for VRC test suite."""

import os
import sys

# ---------------------------------------------------------------------------
# Environment setup — must happen BEFORE importing app so it uses SQLite
# ---------------------------------------------------------------------------
os.environ.pop("DYNAMODB_TABLE", None)
os.environ.setdefault("ANTHROPIC_API_KEY", "test-key-not-real")

# Ensure the project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import app as app_module
from dung_solver import ArgumentationFramework


@pytest.fixture()
def test_db(tmp_path):
    """Point the app at a fresh SQLite database in a temp directory."""
    original = app_module.DB_PATH
    app_module.DB_PATH = str(tmp_path / "test_vrc.db")
    app_module._init_db()
    yield app_module.DB_PATH
    app_module.DB_PATH = original


@pytest.fixture()
def client(test_db):
    """Flask test client backed by the temporary database."""
    app_module.app.config["TESTING"] = True
    with app_module.app.test_client() as c:
        yield c


@pytest.fixture()
def sample_framework():
    """A→B→C chain: A accepted, B rejected, C accepted."""
    af = ArgumentationFramework()
    af.add_argument("A")
    af.add_argument("B")
    af.add_argument("C")
    af.add_attack("A", "B")
    af.add_attack("B", "C")
    return af
