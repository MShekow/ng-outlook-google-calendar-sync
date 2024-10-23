from copy import copy
from datetime import timedelta
from enum import Enum

import pytest
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

from calendar_sync_helper.entities import AbstractCalendarEvent, ComputeActionsInput, \
    OutlookCalendarEvent, ComputeActionsResponse, GoogleCalendarEvent
from calendar_sync_helper.entities import ImplSpecificEvent
from calendar_sync_helper.utils import build_syncblocker_attendees

URL = "/compute-actions"

UNIQUE_SYNC_PREFIX_HEADER_NAME = "X-Unique-Sync-Prefix"
DEFAULT_UNIQUE_SYNC_PREFIX = "syncblocker"
DEFAULT_HEADERS = {
    UNIQUE_SYNC_PREFIX_HEADER_NAME: DEFAULT_UNIQUE_SYNC_PREFIX,
}

EMPTY_INPUT_DATA = jsonable_encoder(ComputeActionsInput(cal1events=[], cal2events=[]))


def test_fail_binary_input_format(test_client: TestClient):
    response = test_client.post(URL, content=b"hello world")
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "json_invalid"


def test_fail_invalid_input_json_format(test_client: TestClient):
    response = test_client.post(URL, json={"some-invalid": "data-format"})
    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "missing"


def test_fail_missing_unique_sync_prefix(test_client: TestClient):
    response = test_client.post(URL, json=EMPTY_INPUT_DATA)
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
    response = test_client.post(URL, json=EMPTY_INPUT_DATA, headers=malformed_sync_prefix_headers)
    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid X-Unique-Sync-Prefix value, must only contain "
                                         "alphanumeric characters and dashes"}


def test_fail_impossible_attendee_padding(test_client: TestClient):
    data = ComputeActionsInput(
        cal1events=[],
        cal2events=[
            AbstractCalendarEvent(
                # Note: ".invalid" and "@" use 9 characters, so we are already at 245+9=254 characters,
                # so together with the "syncblocker" prefix, the limit of 255 characters will be exceeded
                sync_correlation_id=245 * "x",
                title="Test",
                description="some-description",
                location="l1",
                start="2024-10-20T18:00:00Z",
                end="2024-10-20T19:00:00Z",
                is_all_day=False,
                attendees=None,
                show_as=None,
                sensitivity=None
            )
        ]
    )
    response = test_client.post(URL, json=jsonable_encoder(data), headers=DEFAULT_HEADERS)
    assert response.status_code == 400
    error_message: str = response.json()["detail"]
    assert error_message.startswith("Unique sync prefix is too long")


def test_success_empty_data(test_client: TestClient):
    data = ComputeActionsInput(cal1events=[], cal2events=[])
    response = test_client.post(URL, json=jsonable_encoder(data), headers=DEFAULT_HEADERS)
    response_data = ComputeActionsResponse(**response.json())
    assert not response_data.events_to_create
    assert not response_data.events_to_update
    assert not response_data.events_to_delete


def test_success_delete_syncblocker(test_client: TestClient):
    data = ComputeActionsInput(
        cal1events=[
            OutlookCalendarEvent(
                id="realevent",
                subject="Real event",
                body="",
                location="",
                startWithTimeZone="2024-09-09T07:00:00+00:00",
                endWithTimeZone="2024-09-09T08:00:00+00:00",
                requiredAttendees="",
                responseType="organizer",
                isAllDay=False,
                showAs="busy",
                sensitivity="normal"
            ),
            OutlookCalendarEvent(
                id="syncblockerevent",
                subject="Some title",
                body="",
                location="",
                startWithTimeZone="2024-09-09T07:00:00+00:00",
                endWithTimeZone="2024-09-09T08:00:00+00:00",
                requiredAttendees=f"{DEFAULT_UNIQUE_SYNC_PREFIX}@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-040000008200E00174C5B7101A82E008000000000D82237BAD16DB0100000000000000001000000086F553E2D6F24149BC9B223050FB0BD9.invalid;",
                responseType="organizer",
                isAllDay=False,
                showAs="busy",
                sensitivity="normal"
            )
        ],
        cal2events=[]
    )
    response = test_client.post(URL, json=jsonable_encoder(data), headers=DEFAULT_HEADERS)
    response_data = ComputeActionsResponse(**response.json())
    assert not response_data.events_to_create
    assert not response_data.events_to_update
    assert response_data.events_to_delete == [
        AbstractCalendarEvent(sync_correlation_id='syncblockerevent', title='Some title', description='', location='',
                              start="2024-09-09T07:00:00+00:00", end="2024-09-09T08:00:00+00:00",
                              is_all_day=False, attendees=None, show_as='busy', sensitivity='normal')
    ]


@pytest.mark.parametrize(
    "syncblocker_title_prefix",
    ["", "SyncBlocker: "]
)
def test_success_create_syncblocker(test_client: TestClient, syncblocker_title_prefix: str):
    data = ComputeActionsInput(
        cal1events=[],
        cal2events=[
            AbstractCalendarEvent(
                sync_correlation_id="040000008200E00174C5B7101A82E008000000000D82237BAD16DB0100000000000000001000000086F553E2D6F24149BC9B223050FB0BD9",
                title="Test",
                description="some-description",
                location="l1",
                start="2024-10-20T18:00:00Z",
                end="2024-10-20T19:00:00Z",
                is_all_day=False,
                attendees=None,
                show_as=None,
                sensitivity=None
            )
        ]
    )
    headers = copy(DEFAULT_HEADERS)
    headers["X-Syncblocker-Title-Prefix"] = syncblocker_title_prefix
    response = test_client.post(URL, json=jsonable_encoder(data), headers=headers)
    response_data = ComputeActionsResponse(**response.json())
    assert response_data == ComputeActionsResponse(
        events_to_delete=[],
        events_to_update=[],
        events_to_create=[
            AbstractCalendarEvent(
                sync_correlation_id="",
                title=f"{syncblocker_title_prefix}Test",
                description="some-description",
                location="l1",
                start="2024-10-20T18:00:00Z",
                end="2024-10-20T19:00:00Z",
                is_all_day=False,
                attendees=f"{DEFAULT_UNIQUE_SYNC_PREFIX}@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-040000008200E00174C5B7101A82E008000000000D82237BAD16DB0100000000000000001000000086F553E2D6F24149BC9B223050FB0BD9.invalid",
                show_as="busy",
                sensitivity="normal"
            )
        ]
    )


@pytest.mark.parametrize("syncblocker_title_prefix", ["", "SyncBlocker: "])
def test_success_no_action_all_equal(test_client: TestClient, syncblocker_title_prefix: str):
    data = ComputeActionsInput(
        cal1events=[
            OutlookCalendarEvent(
                id="syncblockerevent",
                subject=f"{syncblocker_title_prefix}Some event",
                body="b",
                location="l",
                startWithTimeZone="2024-09-09T07:00:00+00:00",
                endWithTimeZone="2024-09-09T08:00:00+00:00",
                requiredAttendees=f"{DEFAULT_UNIQUE_SYNC_PREFIX}@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-040000008200E00174C5B7101A82E008000000000D82237BAD16DB0100000000000000001000000086F553E2D6F24149BC9B223050FB0BD9.invalid",
                responseType="organizer",
                isAllDay=False,
                showAs="busy",
                sensitivity="normal"
            ),
        ],
        cal2events=[
            AbstractCalendarEvent(
                sync_correlation_id="040000008200E00174C5B7101A82E008000000000D82237BAD16DB0100000000000000001000000086F553E2D6F24149BC9B223050FB0BD9",
                title="Some event",
                description="b",
                location="l",
                start="2024-09-09T07:00:00Z",
                end="2024-09-09T08:00:00Z",
                is_all_day=False,
                attendees=None,
                show_as=None,
                sensitivity=None
            )
        ]
    )
    headers = copy(DEFAULT_HEADERS)
    headers["X-Syncblocker-Title-Prefix"] = syncblocker_title_prefix
    response = test_client.post(URL, json=jsonable_encoder(data), headers=headers)
    response_data = ComputeActionsResponse(**response.json())
    assert response_data == ComputeActionsResponse(
        events_to_delete=[],
        events_to_update=[],
        events_to_create=[]
    )


class EventUpdateOperation(Enum):
    title = 1
    description = 2
    location = 3
    start = 4
    end = 5
    all_day = 6
    show_as = 7
    sensitivity = 8


class EventUpdateSide(Enum):
    calendar1 = 1
    calendar2 = 2


def _update_event_fields(event: ImplSpecificEvent | AbstractCalendarEvent, update_operation: EventUpdateOperation):
    suffix = "changed"
    if isinstance(event, AbstractCalendarEvent):
        if update_operation is EventUpdateOperation.title:
            event.title += suffix
        elif update_operation is EventUpdateOperation.description:
            event.description += suffix
        elif update_operation is EventUpdateOperation.location:
            event.location += suffix
        elif update_operation is EventUpdateOperation.start:
            event.start += timedelta(hours=1)
        elif update_operation is EventUpdateOperation.end:
            event.end += timedelta(hours=1)
        elif update_operation is EventUpdateOperation.all_day:
            event.is_all_day = not event.is_all_day
        elif update_operation is EventUpdateOperation.show_as:
            event.show_as = event.show_as + suffix if event.show_as else suffix
        elif update_operation is EventUpdateOperation.sensitivity:
            event.sensitivity = event.sensitivity + suffix if event.sensitivity else suffix
    elif isinstance(event, OutlookCalendarEvent):
        if update_operation is EventUpdateOperation.title:
            event.subject += suffix
        elif update_operation is EventUpdateOperation.description:
            event.body += suffix
        elif update_operation is EventUpdateOperation.location:
            event.location += suffix
        elif update_operation is EventUpdateOperation.start:
            event.startWithTimeZone += timedelta(hours=1)
        elif update_operation is EventUpdateOperation.end:
            event.endWithTimeZone += timedelta(hours=1)
        elif update_operation is EventUpdateOperation.all_day:
            event.isAllDay = not event.isAllDay
        elif update_operation is EventUpdateOperation.show_as:
            event.showAs = event.showAs + suffix if event.showAs else suffix
        elif update_operation is EventUpdateOperation.sensitivity:
            event.sensitivity = event.sensitivity + suffix if event.sensitivity else suffix
    elif isinstance(event, GoogleCalendarEvent):
        if update_operation is EventUpdateOperation.title:
            event.summary += suffix
        elif update_operation is EventUpdateOperation.description:
            event.description += suffix
        elif update_operation is EventUpdateOperation.location:
            event.location += suffix
        elif update_operation is EventUpdateOperation.start:
            event.start += timedelta(hours=1)
        elif update_operation is EventUpdateOperation.end:
            event.end += timedelta(hours=1)
        elif update_operation is EventUpdateOperation.all_day:
            # GoogleCalendarEvent has no all-day property
            event.start = event.start.date()
            event.end = event.start + timedelta(days=1)
        elif update_operation is EventUpdateOperation.show_as:
            raise NotImplementedError
        elif update_operation is EventUpdateOperation.sensitivity:
            raise NotImplementedError


@pytest.mark.parametrize("syncblocker_title_prefix", ["", "SyncBlocker: "])
@pytest.mark.parametrize(
    "update_operation", [
        EventUpdateOperation.title,
        EventUpdateOperation.description,
        EventUpdateOperation.location,
        EventUpdateOperation.start,
        EventUpdateOperation.end,
        EventUpdateOperation.all_day,
        EventUpdateOperation.show_as,
        EventUpdateOperation.sensitivity
    ]
)
@pytest.mark.parametrize("update_side", [EventUpdateSide.calendar1, EventUpdateSide.calendar2])
def test_success_update_syncblocker(test_client: TestClient, syncblocker_title_prefix: str,
                                    update_operation: EventUpdateOperation,
                                    update_side: EventUpdateSide):
    data = ComputeActionsInput(
        cal1events=[
            OutlookCalendarEvent(
                id="syncblockerevent",
                subject=f"{syncblocker_title_prefix}Some event",
                body="b",
                location="l",
                startWithTimeZone="2024-09-09T07:00:00+00:00",
                endWithTimeZone="2024-09-09T08:00:00+00:00",
                requiredAttendees=f"{DEFAULT_UNIQUE_SYNC_PREFIX}@aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa-040000008200E00174C5B7101A82E008000000000D82237BAD16DB0100000000000000001000000086F553E2D6F24149BC9B223050FB0BD9.invalid",
                responseType="organizer",
                isAllDay=False,
                showAs="busy",
                sensitivity="normal"
            ),
        ],
        cal2events=[
            AbstractCalendarEvent(
                sync_correlation_id="040000008200E00174C5B7101A82E008000000000D82237BAD16DB0100000000000000001000000086F553E2D6F24149BC9B223050FB0BD9",
                title="Some event",
                description="b",
                location="l",
                start="2024-09-09T07:00:00Z",
                end="2024-09-09T08:00:00Z",
                is_all_day=False,
                attendees=None,
                show_as=None,
                sensitivity=None
            )
        ]
    )

    if update_side is EventUpdateSide.calendar1:
        _update_event_fields(data.cal1events[0], update_operation)
    elif update_side is EventUpdateSide.calendar2:
        _update_event_fields(data.cal2events[0], update_operation)

    headers = copy(DEFAULT_HEADERS)
    headers["X-Syncblocker-Title-Prefix"] = syncblocker_title_prefix
    response = test_client.post(URL, json=jsonable_encoder(data), headers=headers)
    response_data = ComputeActionsResponse(**response.json())

    expected_event = copy(data.cal2events[0])
    expected_event.sync_correlation_id = data.cal1events[0].id

    original_show_as = expected_event.show_as
    original_sensitivity = expected_event.sensitivity
    expected_event.show_as = "busy"
    expected_event.sensitivity = "normal"
    if update_operation is EventUpdateOperation.show_as and update_side is EventUpdateSide.calendar2:
        expected_event.show_as = original_show_as
    if update_operation is EventUpdateOperation.sensitivity and update_side is EventUpdateSide.calendar2:
        expected_event.sensitivity = original_sensitivity

    expected_event.attendees = (
        build_syncblocker_attendees(DEFAULT_UNIQUE_SYNC_PREFIX,
                                    real_event_correlation_id=data.cal2events[0].sync_correlation_id))
    if syncblocker_title_prefix:
        expected_event.title = f"{syncblocker_title_prefix}{expected_event.title}"

    assert response_data == ComputeActionsResponse(
        events_to_delete=[],
        events_to_update=[expected_event],
        events_to_create=[]
    )
