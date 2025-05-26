import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from app.main import app
from fastapi import FastAPI
from unittest.mock import AsyncMock
from app.api.auth_guard import auth_guard
from app.tests.fixtures.user import *
from app.tests.fixtures.scan import *
from app.tests.fixtures.products import *
from app.tests.fixtures.location import mock_location_reverse_geocode
from app.tests.fixtures.auth import mock_auth_httpx_client
from app.tests.fixtures.billing import *
from app.tests.constants.user import UserTestConstants
import asyncio


@pytest.fixture(scope="function")
def mock_auth_user_data():
    """Fixture providing mock user data structure from auth_guard."""
    return {"sub": UserTestConstants.MOCK_USER_ID.value}


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def mock_auth_guard_override(mock_auth_user_data):
    """Fixture providing a mock async function to override auth_guard dependency."""

    async def _mock_auth_guard():
        return mock_auth_user_data

    return _mock_auth_guard


@pytest_asyncio.fixture(scope="function", loop_scope="function")
async def authenticated_client(mock_auth_guard_override):
    """Fixture providing a TestClient with auth_guard dependency overridden."""
    app.dependency_overrides[auth_guard] = mock_auth_guard_override

    with TestClient(app) as c:
        yield c

    # Clean up overrides after the test finished
    app.dependency_overrides.clear()
