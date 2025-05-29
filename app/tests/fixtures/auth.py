import pytest


@pytest.fixture(scope="function")
def mock_auth_httpx_client(mocker):
    """Fixture to patch and provide a mock for httpx client."""
    mock = mocker.patch("app.api.endpoints.auth.httpx.AsyncClient.post")
    return mock
