"""Test settings — inherits everything from main settings, but disables auth for tests."""

from core.settings import *  # noqa: F401, F403

REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] = []  # type: ignore[name-defined]  # noqa: F405
REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"] = [  # type: ignore[name-defined]  # noqa: F405
    "rest_framework.authentication.SessionAuthentication",
]

# Override permission classes on all views during tests
REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"] = [  # type: ignore[name-defined]  # noqa: F405
    "rest_framework.permissions.AllowAny",
]
