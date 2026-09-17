"""
ClassFellow - Pytest Configuration & Test Fixtures
===================================================
Provides configured in-memory and temp-file SQLite database fixtures.
"""

import os
import sys
import pytest

# Ensure project root is in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

WEB_ROOT = os.path.join(PROJECT_ROOT, "classfellow_web")
if WEB_ROOT not in sys.path:
    sys.path.insert(0, WEB_ROOT)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
os.environ.setdefault("DJANGO_DB_ENGINE", "sqlite")

from database import get_connection  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def setup_django_environment():
    """Ensures Django app is initialized and database schema is migrated before any tests run."""
    import django
    django.setup()
    from django.core.management import call_command
    call_command("migrate", interactive=False)


@pytest.fixture
def temp_db_path(tmp_path):
    """Returns a temporary database file path for isolated disk/WAL tests."""
    db_file = tmp_path / "test_classfellow.db"
    return str(db_file)


@pytest.fixture
def db_connection(temp_db_path):
    """Provides a fresh, pragma-configured SQLite connection using a temporary file (full WAL support)."""
    conn = get_connection(temp_db_path)
    yield conn
    conn.close()


@pytest.fixture
def memory_db_connection():
    """Provides an ultra-fast in-memory SQLite connection with Decimal converters and foreign keys."""
    conn = get_connection(":memory:")
    yield conn
    conn.close()
