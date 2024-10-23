import pytest
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

from calendar_sync_helper.entities import CalendarEventList, AbstractCalendarEvent
from tests import parse_abstract_calendar_event_list
from tests.test_data import load_test_data

URL = "/extract-events"
UNIQUE_SYNC_PREFIX_HEADER_NAME = "X-Unique-Sync-Prefix"
DEFAULT_UNIQUE_SYNC_PREFIX = "syncblocker"
DEFAULT_HEADERS = {
    UNIQUE_SYNC_PREFIX_HEADER_NAME: DEFAULT_UNIQUE_SYNC_PREFIX,
    "X-Sync-Events-Without-Attendees": "1"
}

EMPTY_EVENT_LIST = jsonable_encoder(CalendarEventList(events=[]))


def test_fail_binary_input_format(test_client: TestClient):
    response = test_client.post(URL, content=b"hello world")
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "json_invalid"


def test_fail_invalid_input_json_format(test_client: TestClient):
    response = test_client.post(URL, json={"some-invalid": "data-format"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "missing"


def test_fail_missing_unique_sync_prefix(test_client: TestClient):
    response = test_client.post(URL, json=EMPTY_EVENT_LIST)
    assert response.status_code == 400
    assert response.json() == {"detail": "You must provide the X-Unique-Sync-Prefix header"}


@pytest.mark.parametrize(
    "malformed_sync_prefix_headers",
    [
        {UNIQUE_SYNC_PREFIX_HEADER_NAME: "special-%-chars"},
        {UNIQUE_SYNC_PREFIX_HEADER_NAME: "double--dashes"},
        {UNIQUE_SYNC_PREFIX_HEADER_NAME: "-dash-start"},
        {UNIQUE_SYNC_PREFIX_HEADER_NAME: "dash-end-"},
    ],
)
def test_fail_malformed_unique_sync_prefix(test_client: TestClient, malformed_sync_prefix_headers: dict[str, str]):
    response = test_client.post(URL, json=EMPTY_EVENT_LIST, headers=malformed_sync_prefix_headers)
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid X-Unique-Sync-Prefix value, must only contain "
                                         "alphanumeric characters and dashes"}


def test_success_simple_outlook_events(test_client: TestClient):
    """
    Uploads two Outlook events, one is an all-day event, one is not, both should be returned.
    """
    test_events = load_test_data("simple-outlook-events")

    response = test_client.post(URL, headers=DEFAULT_HEADERS, json={"events": test_events})
    assert response.status_code == 200
    calendar_events = parse_abstract_calendar_event_list(response.json())
    assert calendar_events == [
        AbstractCalendarEvent(
            sync_correlation_id="AAMkAGRiOTlhZjY3LTQzNWUtNGM0Ny05MGMwLWFmNDBlNzAxMDQ5OQBGAAAAAADBo9O3K16XQLoK7AG7_ka5BwARhE7LLMewTpXLsn71Fh8UAAAAAAENAAARhE7LLMewTpXLsn71Fh9UAAIRfOSpAAA=",
            title="Fokuszeit",
            description="body-Fokuszeit",
            location="l",
            start="2024-10-18T13:00:00Z",
            end="2024-10-18T15:00:00Z",
            is_all_day=False,
            attendees=None,
            show_as="busy",
            sensitivity="normal"
        ),
        AbstractCalendarEvent(
            sync_correlation_id="AAMkAGRiOTlhZjY3LTQzNWUtNGM0Ny05MGMwLWFmNDBlNzAxMZQ5OQBGAAAAAADBo9O3K16XQLoK7AG7_ka5BwARhE7LLMewTpXLsn71Fh9UAADAKPwgAAARhE7LLMewTpXLsn71Fh9UAAIb2raZAAA=",
            title="Allday-Test",
            description="body-allday",
            location="",
            start="2024-10-20T00:00:00Z",
            end="2024-10-21T00:00:00Z",
            is_all_day=True,
            attendees=None,
            show_as="free",
            sensitivity="normal"
        )
    ]


def test_success_simple_google_events(test_client: TestClient):
    """
    Uploads two Google events, one is an all-day event, one is not, both should be returned.
    """
    test_events = load_test_data("simple-google-events")

    response = test_client.post(URL, headers=DEFAULT_HEADERS, json={"events": test_events})
    assert response.status_code == 200
    calendar_events = parse_abstract_calendar_event_list(response.json())
    assert calendar_events == [
        AbstractCalendarEvent(
            sync_correlation_id="0vj05aaoqlk1878pb4thqldma3_20241020T180000Z",  # Note: _ was removed
            title="Test",
            description="some-description",
            location="l1",
            start="2024-10-20T18:00:00Z",
            end="2024-10-20T19:00:00Z",
            is_all_day=False,
            attendees=None,
            show_as=None,
            sensitivity=None
        ),
        AbstractCalendarEvent(
            sync_correlation_id="2p46iccjfho9etduhmc12171rt",
            title="Allday",
            description="allday-body",
            location="loc",
            start="2024-10-21T00:00:00Z",
            end="2024-10-22T00:00:00Z",
            is_all_day=True,
            attendees=None,
            show_as=None,
            sensitivity=None
        )
    ]

def test_success_normal_and_sb_event(test_client: TestClient):
    """
    Uploads 3 Outlook events, one is a syncblocker for a matching prefix, one is a syncblocker without matching prefix,
    the third one is a regular event. The syncblocker with the matching prefix should not be returned.
    """
    test_events = load_test_data("normal-and-sb-event")
    response = test_client.post(URL, headers=DEFAULT_HEADERS, json={"events": test_events})
    assert response.status_code == 200
    calendar_events = parse_abstract_calendar_event_list(response.json())
    assert len(calendar_events) == 2
    assert calendar_events[0].title == "Non-matching SyncBlocker"
    assert calendar_events[1].title == "Fokuszeit"
