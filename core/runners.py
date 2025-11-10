import os
import unittest
from typing import Any

import django
from django.apps import apps
from django.conf import settings
from django.db import connection, connections
from django.test.runner import DiscoverRunner


class CustomTestRunner(DiscoverRunner):
    """
    Custom test runner to:
    1. Use SQLite3 as the test database
    2. Drop and recreate the test database before each run
    3. Automatically create tables without requiring migrations
    """

    def setup_databases(self, *args: Any, **kwargs: Any) -> Any:
        """Recreate SQLite3 test database and manually create all tables."""
        self.create_test_media_folder()
        self.create_all_tables()

        print(f"✅ SQLite3 test database initialized successfully!")

        return super().setup_databases(*args, **kwargs)

    def teardown_databases(self, *args: Any, **kwargs: Any) -> None:
        """Clean up all data from all tables after tests."""
        try:
            # ✅ Ensure the database connection is still active
            if connection.connection is not None:
                self.clear_all_tables()
        except Exception as e:
            print(f"⚠️ Warning: Could not clear tables. Reason: {e}")
        self.cleanup_test_files()
        self.force_close_db()

    def create_all_tables(self) -> None:
        """Create tables only if they do not already exist in the database."""
        existing_tables = self.get_existing_tables()

        with connection.schema_editor() as schema_editor:
            for model in apps.get_models():
                table_name = model._meta.db_table

                if table_name not in existing_tables:
                    try:
                        schema_editor.create_model(model)
                    except Exception as e:
                        print(f"❌ Error creating table {table_name}: {e}")
                else:
                    print(f"⚠️ Table already exists: {table_name}, skipping creation.")
            print(f"✅ Created all table")

    def clear_all_tables(self) -> None:
        """Deletes all data from all tables, including built-in Django tables."""
        with connection.cursor() as cursor:
            # ✅ Disable foreign key constraints (SQLite only)
            cursor.execute("PRAGMA foreign_keys = OFF;")
            existing_tables = self.get_existing_tables()

            for table_name in existing_tables:
                try:
                    cursor.execute(f"DELETE FROM {table_name};")  # Delete all rows
                except Exception as e:
                    print(f"⚠️ Failed to clear {table_name}: {e}")

            # Re-enable foreign key constraints
            cursor.execute("PRAGMA foreign_keys = ON;")

    def get_existing_tables(self) -> set[str]:
        """Retrieves all tables in the database."""
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            return {row[0] for row in cursor.fetchall()}

    def force_close_db(self) -> None:
        """Closes all open database connections to force reset."""
        for conn in connections.all():
            conn.close()

    def create_test_media_folder(self) -> None:
        """Ensure the test media folder exists."""
        media_dir = os.path.join(settings.BASE_DIR, settings.MEDIA_ROOT)
        if not os.path.exists(media_dir):
            os.makedirs(media_dir)

    def cleanup_test_files(self) -> None:
        """Delete the entire `test_media/` directory after tests."""
        import shutil

        media_dir = os.path.join(settings.BASE_DIR, settings.MEDIA_ROOT)

        if os.path.exists(media_dir):
            shutil.rmtree(media_dir)
            print(f"🗑 Deleted test files in {media_dir}")

    def build_suite(
        self, test_labels: Any = None, extra_tests: Any = None, **kwargs: Any
    ) -> unittest.TestSuite:
        """Dynamically discover test files in all installed apps."""
        suite = unittest.TestSuite()
        test_loader = unittest.defaultTestLoader

        if test_labels:
            # ✅ If specific tests are requested, load only those
            for label in test_labels:
                try:
                    suite.addTests(test_loader.loadTestsFromName(label))
                except ImportError as e:
                    print(f"❌ Test not found: {label} ({e})")
        else:
            # ✅ Automatically detect all `tests/` folders in installed apps
            for app_config in apps.get_app_configs():
                test_dir = os.path.join(app_config.path, "tests")
                if os.path.exists(test_dir):
                    suite.addTests(test_loader.discover(test_dir, pattern="test_*.py"))

        return suite


# ✅ Ensure Django initializes properly
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()
