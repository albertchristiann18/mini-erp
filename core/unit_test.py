# mypy: disable-error-code="name-defined"

from core.settings import *

print("⚠️ Switching to SQLite3 for unit tests")

in_memory_database_config = {
    "ENGINE": "django.db.backends.sqlite3",
    "NAME": "file::memory:?cache=shared",  # In-memory SQLite3 DB (faster tests)
    "OPTIONS": {
        "timeout": 20,  # Increase timeout for database locks (default: 5s)
    },
    "TEST": {
        "MIRROR": None,  # Ensures test DB is separate from the default
        "NAME": ":memory:",  # ✅ Explicitly use in-memory for tests
    },
}
for db_name in DATABASES:
    DATABASES[db_name] = in_memory_database_config

DEBUG = False

# Unit Test Runners
TEST_RUNNER = "settings.runners.CustomTestRunner"
