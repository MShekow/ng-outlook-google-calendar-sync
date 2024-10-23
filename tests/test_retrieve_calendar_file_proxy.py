import pytest
from fastapi.testclient import TestClient

URL = "/retrieve-calendar-file-proxy"


@pytest.mark.parametrize(
    "incomplete_headers",
    [
        {},
        {"X-File-Location": "https://some.location"},
        {"X-Auth-Header-Name": "Foo"},
        {"X-File-Location": "https://some.location", "X-Auth-Header-Name": "Foo"},
        {"X-File-Location": "https://some.location", "X-Auth-Header-Value": "Foo"},
    ],
)
def test_fail_missing_headers(test_client: TestClient, incomplete_headers: dict[str, str]):
    response = test_client.get(URL, headers=incomplete_headers)
    assert response.status_code == 400
    assert response.json() == {"detail": "Missing required headers"}


@pytest.mark.parametrize(
    "invalid_file_location",
    [
        "foo://bar",
        "some-string",
        "ftp://example.com",
        "//example.com/foo/bar",
    ],
)
def test_fail_invalid_url(test_client: TestClient, invalid_file_location: str):
    headers = {
        "X-File-Location": invalid_file_location,
        "X-Auth-Header-Name": "Foo",
        "X-Auth-Header-Value": "Bar",
    }
    response = test_client.get(URL, headers=headers)
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid file location, must be a valid http(s) URL"}


def test_fail_invalid_content(test_client: TestClient):
    headers = {
        "X-File-Location": "https://www.google.com",  # serves HTML, not JSON
        "X-Auth-Header-Name": "Foo",
        "X-Auth-Header-Value": "Bar",
    }
    response = test_client.get(URL, headers=headers)
    assert response.status_code == 400
    assert response.json() == {"detail": "Failed to parse JSON content: Expecting value: line 1 column 1 (char 0)"}


def test_fail_large_content(test_client: TestClient):
    headers = {
        "X-File-Location": "https://ash-speed.hetzner.com/100MB.bin",
        "X-Auth-Header-Name": "Foo",
        "X-Auth-Header-Value": "Bar",
    }
    response = test_client.get(URL, headers=headers)
    assert response.status_code == 413
    assert response.json() == {"detail": "File size exceeds maximum size limit"}


def test_success(test_client: TestClient):
    headers = {
        "X-File-Location": "https://services.gradle.org/versions/all",
        "X-Auth-Header-Name": "Foo",
        "X-Auth-Header-Value": "Bar",
    }
    response = test_client.get(URL, headers=headers)
    assert response.status_code == 200
