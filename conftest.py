from unittest.mock import patch

import pytest


@pytest.fixture(autouse=True)
def disable_permissions():
    """Disable DRF permission checks in all tests."""
    with patch("core.permissions.IsStaffOrReadOnly.has_permission", return_value=True):
        with patch("rest_framework.permissions.IsAuthenticated.has_permission", return_value=True):
            yield
