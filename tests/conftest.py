from datetime import datetime
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from main import app


@pytest.fixture
def test_client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def mock_date(request):
    date_format = '%Y-%m-%dT%H:%M:%S%z'
    mock_datetime = datetime.strptime(request.param, date_format)

    with mock.patch("calendar_sync_helper.utils.GET_UTC_DATE_FUNCTION", return_value=mock_datetime):
        yield
