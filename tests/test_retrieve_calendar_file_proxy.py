import os

import pytest
from fastapi.testclient import TestClient
from pytest_httpserver import HTTPServer

from calendar_sync_helper.cryptography_utils import encrypt
from tests import fix_file_location_for_localhost

URL = "/retrieve-calendar-file-proxy"

INVALID_FILE_LOCATIONS = [
    "foo://bar",
    "localhost",
    "http://localhost",  # See https://github.com/python-validators/validators/issues/392 for why this is invalid
    "some-string",
    "ftp://example.com",
    "//example.com/foo/bar",
]

UNREACHABLE_FILE_LOCATIONS = [
    "http://doesnotexistforsure.com",
    "https://www.google.com:1337"
]

INVALID_GITHUB_PAT = "foo"
VALID_GITHUB_PAT = os.environ.get("GITHUB_INTEGRATION_TEST_PAT")
if not VALID_GITHUB_PAT:
    raise ValueError("GitHub PAT for integration test is missing")

GITHUB_VALID_OWNER_REPO_BRANCH = os.environ.get("GITHUB_INTEGRATION_TEST_OWNER_REPO_BRANCH")
if not GITHUB_VALID_OWNER_REPO_BRANCH:
    raise ValueError("GitHub owner/repo/branch value for integration test is missing")


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


@pytest.mark.parametrize("invalid_file_location", INVALID_FILE_LOCATIONS)
def test_fail_invalid_url(test_client: TestClient, invalid_file_location: str):
    headers = {
        "X-File-Location": invalid_file_location,
        "X-Auth-Header-Name": "Foo",
        "X-Auth-Header-Value": "Bar",
    }
    response = test_client.get(URL, headers=headers)
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid file location, must be a valid http(s) URL"}


@pytest.mark.parametrize("unreachable_file_location", UNREACHABLE_FILE_LOCATIONS)
def test_fail_unreachable_file_location(test_client: TestClient, unreachable_file_location: str):
    headers = {
        "X-File-Location": unreachable_file_location,
        "X-Auth-Header-Name": "Foo",
        "X-Auth-Header-Value": "Bar",
    }
    response = test_client.get(URL, headers=headers)
    assert response.status_code == 400
    assert response.json()["detail"].startswith("Failed to retrieve file:")


def test_fail_invalid_content(test_client: TestClient):
    headers = {
        "X-File-Location": "https://www.google.com",  # serves HTML, not JSON
        "X-Auth-Header-Name": "Foo",
        "X-Auth-Header-Value": "Bar",
    }
    response = test_client.get(URL, headers=headers)
    assert response.status_code == 400
    assert response.json() == {
        "detail": "Failed to parse JSON content: JSONDecodeError('Expecting value: line 1 column 1 (char 0)')"
    }


def test_fail_large_content(test_client: TestClient):
    headers = {
        "X-File-Location": "https://ash-speed.hetzner.com/100MB.bin",
        "X-Auth-Header-Name": "Foo",
        "X-Auth-Header-Value": "Bar",
    }
    response = test_client.get(URL, headers=headers)
    assert response.status_code == 413
    assert response.json() == {"detail": "File size exceeds maximum size limit"}


def test_fail_plaintext_data_with_encryption_key(test_client: TestClient, httpserver: HTTPServer):
    headers = {
        "X-File-Location": httpserver.url_for("/file.txt"),
        "X-Auth-Header-Name": "Foo",
        "X-Auth-Header-Value": "Bar",
        "X-Data-Encryption-Password": "foo"
    }
    headers["X-File-Location"] = fix_file_location_for_localhost(headers["X-File-Location"])

    httpserver.expect_request("/file.txt", method="GET").respond_with_data(response_data="[]", status=200)

    response = test_client.get(URL, headers=headers)
    assert response.status_code == 400
    assert response.json() == {"detail": "Unable to decrypt data, unexpected error occurred: "
                                         "ValueError('initialization_vector must be between 8 and 128 bytes "
                                         "(64 and 1024 bits).')"}


def test_fail_tampered_encrypted_data(test_client: TestClient, httpserver: HTTPServer):
    password = "foo"
    headers = {
        "X-File-Location": httpserver.url_for("/file.txt"),
        "X-Auth-Header-Name": "Foo",
        "X-Auth-Header-Value": "Bar",
        "X-Data-Encryption-Password": password
    }
    headers["X-File-Location"] = fix_file_location_for_localhost(headers["X-File-Location"])

    plaintext_data_to_return = "[]"
    encrypted_plaintext_data = encrypt(plaintext=plaintext_data_to_return, password=password)
    # tamper with the encrypted data
    tampered_encrypted_plaintext_data = bytearray(encrypted_plaintext_data)
    tampered_encrypted_plaintext_data[30] ^= 0x01  # Flip a bit
    tampered_encrypted_plaintext_data = bytes(tampered_encrypted_plaintext_data)

    httpserver.expect_request("/file.txt", method="GET").respond_with_data(
        response_data=tampered_encrypted_plaintext_data, status=200)

    response = test_client.get(URL, headers=headers)
    assert response.status_code == 400
    assert response.json() == {"detail": "Unable to decrypt data, either wrong password or data was manipulated"}


def test_fail_wrong_encryption_password(test_client: TestClient, httpserver: HTTPServer):
    password = "foo"
    headers = {
        "X-File-Location": httpserver.url_for("/file.txt"),
        "X-Auth-Header-Name": "Foo",
        "X-Auth-Header-Value": "Bar",
        "X-Data-Encryption-Password": password + "invalid suffix"
    }
    headers["X-File-Location"] = fix_file_location_for_localhost(headers["X-File-Location"])

    plaintext_data_to_return = "[]"
    encrypted_plaintext_data = encrypt(plaintext=plaintext_data_to_return, password=password)

    httpserver.expect_request("/file.txt", method="GET").respond_with_data(
        response_data=encrypted_plaintext_data, status=200)

    response = test_client.get(URL, headers=headers)
    assert response.status_code == 400
    assert response.json() == {"detail": "Unable to decrypt data, either wrong password or data was manipulated"}


@pytest.mark.parametrize("github_pat,url", [
    (INVALID_GITHUB_PAT, f"https://github.com/{GITHUB_VALID_OWNER_REPO_BRANCH}/some-file"),
    (VALID_GITHUB_PAT, f"https://github.com/"),
    (VALID_GITHUB_PAT, f"https://github.com/owner"),
    (VALID_GITHUB_PAT, f"https://github.com/owner/repo"),
    (VALID_GITHUB_PAT, f"https://github.com/owner/repo/branch"),
    (VALID_GITHUB_PAT, f"https://github.com/owner/repo/branch/"),
])
def test_fail_github_invalid_url_or_pat(test_client: TestClient, github_pat: str, url: str):
    headers = {
        "X-File-Location": url,
        "X-Auth-Header-Name": "PAT",
        "X-Auth-Header-Value": github_pat,
    }
    response = test_client.get(URL, headers=headers)
    assert response.status_code == 400
    response_data = response.json()
    if github_pat == INVALID_GITHUB_PAT:
        assert response_data["detail"].startswith("Failed to retrieve file: invalid GitHub PAT or owner/repo was "
                                                  "provided")
    else:
        assert response_data["detail"].startswith("Failed to retrieve file: URL does not match the expected pattern")


def test_fail_github_nonexistent_file(test_client: TestClient):
    headers = {
        "X-File-Location": f"https://github.com/{GITHUB_VALID_OWNER_REPO_BRANCH}/does-not-exist.txt",
        "X-Auth-Header-Name": "PAT",
        "X-Auth-Header-Value": VALID_GITHUB_PAT,
    }
    response = test_client.get(URL, headers=headers)
    assert response.status_code == 400
    assert response.json() == {"detail": "Failed to retrieve file: downloading file from GitHub failed, it "
                                         "does not exist"}


@pytest.mark.parametrize("file_path,password", [
    ("files/plaintext-empty-events.json", "some-password"),
    ("files/encrypted-with-foo-empty-events.bin", "")
])
def test_fail_github_encryption_plaintext_mismatch(test_client: TestClient, file_path: str, password: str):
    headers = {
        "X-File-Location": f"https://github.com/{GITHUB_VALID_OWNER_REPO_BRANCH}/{file_path}",
        "X-Auth-Header-Name": "PAT",
        "X-Auth-Header-Value": VALID_GITHUB_PAT,
        "X-Data-Encryption-Password": password
    }
    response = test_client.get(URL, headers=headers)
    assert response.status_code == 400
    if password:
        assert response.json() == {"detail": "Unable to decrypt data, unexpected error occurred: "
                                             "ValueError('initialization_vector must be between 8 and 128 bytes "
                                             "(64 and 1024 bits).')"}

    else:
        assert response.json() == {"detail": "Unable to decode binary response data to text"}


def test_fail_github_large_content(test_client: TestClient):
    headers = {
        "X-File-Location": f"https://github.com/{GITHUB_VALID_OWNER_REPO_BRANCH}/files/10-mb-random-binary.bin",
        "X-Auth-Header-Name": "PAT",
        "X-Auth-Header-Value": VALID_GITHUB_PAT
    }
    response = test_client.get(URL, headers=headers)
    assert response.status_code == 400
    assert response.json() == {"detail": "Failed to retrieve file: unexpected error occurred while "
                                         "downloading file from GitHub: ValueError('Content is too large "
                                         "(10485760 bytes)')"}


def test_success(test_client: TestClient):
    headers = {
        "X-File-Location": "https://services.gradle.org/versions/all",
        "X-Auth-Header-Name": "Foo",
        "X-Auth-Header-Value": "Bar",
    }
    response = test_client.get(URL, headers=headers)
    assert response.status_code == 200


def test_success_with_encryption_password(test_client: TestClient, httpserver: HTTPServer):
    password = "foo"
    headers = {
        "X-File-Location": httpserver.url_for("/file.txt"),
        "X-Auth-Header-Name": "Foo",
        "X-Auth-Header-Value": "Bar",
        "X-Data-Encryption-Password": password
    }
    headers["X-File-Location"] = fix_file_location_for_localhost(headers["X-File-Location"])

    plaintext_data_to_return = "[]"
    encrypted_plaintext_data = encrypt(plaintext=plaintext_data_to_return, password=password)

    httpserver.expect_request("/file.txt", method="GET").respond_with_data(
        response_data=encrypted_plaintext_data, status=200)

    response = test_client.get(URL, headers=headers)
    assert response.status_code == 200
    assert response.text == plaintext_data_to_return


@pytest.mark.parametrize("file_path,password", [
    ("files/plaintext-empty-events.json", ""),
    ("files/encrypted-with-foo-empty-events.bin", "foo")
])
def test_success_github(test_client: TestClient, file_path: str, password: str):
    headers = {
        "X-File-Location": f"https://github.com/{GITHUB_VALID_OWNER_REPO_BRANCH}/{file_path}",
        "X-Auth-Header-Name": "PAT",
        "X-Auth-Header-Value": VALID_GITHUB_PAT,
        "X-Data-Encryption-Password": password
    }
    response = test_client.get(URL, headers=headers)
    assert response.status_code == 200
    assert response.text == "[]"
