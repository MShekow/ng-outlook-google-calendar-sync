import json
import re
from datetime import UTC, datetime
from typing import Optional, Tuple

import httpx
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from github import GithubException

from calendar_sync_helper.constants import MAX_FILE_SIZE_LIMIT_BYTES
from calendar_sync_helper.cryptography_utils import encrypt
from calendar_sync_helper.entities.entities_v1 import ImplSpecificEvent, GoogleCalendarEvent, AbstractCalendarEvent, \
    ComputeActionsInput
from calendar_sync_helper.github_client import GitHubClient


def _get_actual_utc_datetime() -> datetime:
    return datetime.now(tz=UTC)


# Temporarily patched by pytest fixture "mock_date" during automated tests
GET_UTC_DATE_FUNCTION = _get_actual_utc_datetime


def get_current_utc_date() -> datetime:
    return GET_UTC_DATE_FUNCTION()


def extract_attendees(event: ImplSpecificEvent) -> list[str]:
    if isinstance(event, GoogleCalendarEvent):
        split_char = ","
        attendees = event.attendees
    else:  # Outlook
        split_char = ";"
        attendees = event.requiredAttendees

    # note: the 'if bool(attendee)' handles situations like "foo@bar;"
    return [attendee.strip() for attendee in attendees.split(split_char) if bool(attendee)]


def is_syncblocker_event(event: ImplSpecificEvent, unique_sync_prefix: str) -> bool:
    attendees = extract_attendees(event)

    if len(attendees) != 1:
        return False

    attendee = attendees[0]
    return attendee.endswith(".invalid") and attendee.startswith(f"{unique_sync_prefix}@")


def get_id_from_attendees(event: ImplSpecificEvent) -> str:
    """
    Assumes that the event is a SyncBlocker event. Returns the id stored in the attendee's email address.
    """
    attendees = extract_attendees(event)
    # attendees[0] has the form "<sync-prefix>@<id-with-padding>.invalid"
    id_with_padding_and_invalid_domain = attendees[0].split("@")[1]
    id_with_padding = id_with_padding_and_invalid_domain[:-len(".invalid")]
    # id_with_padding should e.g. look like this: "aaaaaaa-<actual-id>"
    id_parts = id_with_padding.split("-")
    if len(id_parts) != 2:
        e = AbstractCalendarEvent.from_implementation(event)
        raise HTTPException(status_code=400, detail=f"Attendee email for event '{e.title}' (start: '{e.start}') "
                                                    f"has an invalid syncblocker attendee email that lacks "
                                                    f"padding: '{attendees[0]}'")

    return id_parts[1]


def separate_syncblocker_events(events: list[ImplSpecificEvent],
                                unique_sync_prefix: str) -> tuple[list[ImplSpecificEvent], list[ImplSpecificEvent]]:
    cal1real = []
    cal1sb = []

    for event in events:
        if is_syncblocker_event(event, unique_sync_prefix):
            cal1sb.append(event)
        else:
            cal1real.append(event)

    return cal1real, cal1sb


def build_syncblocker_attendees(unique_sync_prefix: str, real_event_correlation_id: str) -> str:
    """
    Creates a string with a single email address of the form:
    <unique-sync-prefix>@<padding>-<cleaned-real-event-correlation-id>.invalid

    The reason why we add a padding is that some calendar providers (so far, only Outlook), may actually try to send
    event invitation emails when creating an event in the calendar (Googles does NOT). In case of Outlook, this would
    cause notification emails in your account, complaining that these invitation mails cannot be delivered (because of
    the ".invalid" domain). However, these event invitation mails only seem to be sent if the host is rather short.
    By adding a padding (making the DNS longer), the problem no longer occurs.
    """
    cleaned_real_event_correlation_id = clean_id(real_event_correlation_id)
    attendee_address_without_padding = f"{unique_sync_prefix}@{cleaned_real_event_correlation_id}.invalid"
    number_of_padding_chars = 255 - len(attendee_address_without_padding)
    if number_of_padding_chars < 2:  # 2 because we want to add at least "a-"
        raise HTTPException(status_code=400, detail=f"Unique sync prefix is too long to build an attendee email. "
                                                    f"For event with ID '{cleaned_real_event_correlation_id}' "
                                                    f"(length:  {len(cleaned_real_event_correlation_id)}) there are "
                                                    f"too few padding chars left: {number_of_padding_chars}. "
                                                    f"Please shorten your unique sync prefix")

    padding = "a" * (number_of_padding_chars - 1)
    return f"{unique_sync_prefix}@{padding}-{cleaned_real_event_correlation_id}.invalid"


DEFAULT_ANONYMIZED_TITLE_PLACEHOLDER = "Blocker"


def get_syncblocker_title(syncblocker_title_prefix: Optional[str], event_title: str,
                          anonymized_title_placeholder: Optional[str]) -> str:
    title_placeholder = anonymized_title_placeholder if anonymized_title_placeholder else ""  # avoid "None" in title
    syncblocker_title_prefix = syncblocker_title_prefix if syncblocker_title_prefix else ""  # avoid "None" in title

    if not event_title:
        event_title = title_placeholder or DEFAULT_ANONYMIZED_TITLE_PLACEHOLDER

    return syncblocker_title_prefix + event_title


def fix_outlook_specific_field_defaults(event: AbstractCalendarEvent):
    if event.show_as is None:
        event.show_as = "busy"

    if event.sensitivity is None:
        event.sensitivity = "normal"


def has_matching_title(syncblocker_event_title: str, event_title: str, syncblocker_title_prefix: Optional[str],
                       anonymized_title_placeholder: Optional[str]) -> bool:
    if event_title:
        if syncblocker_title_prefix:
            return syncblocker_event_title == syncblocker_title_prefix + event_title
        return syncblocker_event_title == event_title

    # data is anonymized
    title_placeholder = anonymized_title_placeholder or DEFAULT_ANONYMIZED_TITLE_PLACEHOLDER
    if syncblocker_title_prefix:
        return syncblocker_event_title == syncblocker_title_prefix + title_placeholder
    return syncblocker_event_title == title_placeholder


def get_boolean_header_value(raw_header: Optional[str]) -> bool:
    if not raw_header:
        return False

    if raw_header.lower() in ["true", "yes", "y", "1"]:
        return True

    if raw_header.lower() in ["false", "no", "n", "0"]:
        return False

    raise HTTPException(status_code=400, detail=f"Invalid boolean header value: {raw_header}")


def is_valid_sync_prefix(sync_prefix: str) -> bool:
    """
    Validates that the string contains only 0-9, a-z, A-Z, and "-" (dashes).
    The string may not begin or end with a dash, and there may only be one consecutive dash at a time.
    """
    pattern = r'^[a-zA-Z0-9]+(-[a-zA-Z0-9]+)*$'
    return bool(re.match(pattern, sync_prefix))


def clean_id(unclean_id: str) -> str:
    # Remove any character that is not a-z, A-Z, or 0-9
    cleaned_id = re.sub(r'[^a-zA-Z0-9]', '', unclean_id)
    # Some calendar providers (Outlook) may use mixed upper/lower case, but we cannot and should not use mixed case in
    # the (case-INsensitive) attendee email address
    return cleaned_id.lower()


def filter_past_events(input_data: ComputeActionsInput):
    now = get_current_utc_date()

    input_data.cal1events = \
        [e for e in input_data.cal1events if AbstractCalendarEvent.from_implementation(e).start >= now]
    input_data.cal2events = [e for e in input_data.cal2events if e.start >= now]


async def download_file_contents(x_file_location: str, x_auth_header_name: str,
                                 x_auth_header_value: str) -> Tuple[bytes, Optional[str]]:
    """
    Downloads the data and returns it as raw bytes, with an optional hint of the encoding (e.g. "utf-8").
    Raises HTTPException if something goes wrong.
    """
    try:
        if x_file_location.startswith("https://github.com/"):
            try:
                github_client = GitHubClient(url=x_file_location, personal_access_token=x_auth_header_value)
            except ValueError as e:  # GitHub URL is malformed
                raise HTTPException(status_code=400, detail=f"Failed to retrieve file: {e}")

            try:
                github_client.check_data_and_pat_validity()
            except GithubException as e:
                raise HTTPException(status_code=400, detail=f"Failed to retrieve file: invalid GitHub PAT or owner/repo "
                                                            f"was provided. Status {e.status} was returned, with "
                                                            f"message '{e.message}'")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to retrieve file: unexpected error while checking "
                                                            f"GitHub data and PAT: {e!r}")

            try:
                binary_data = github_client.download_file()  # the file at <path> could not exist
            except GithubException as e:
                raise HTTPException(status_code=400, detail=f"Failed to retrieve file: downloading file from GitHub "
                                                            f"failed: {e.message or e.status}")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to retrieve file: unexpected error occurred while "
                                                            f"downloading file from GitHub: {e!r}")

            if not binary_data:
                raise HTTPException(status_code=400, detail=f"Failed to retrieve file: downloading file from GitHub "
                                                            f"failed, it does not exist")

            return binary_data, None
        else:
            async with httpx.AsyncClient() as client:
                headers = {
                    x_auth_header_name: x_auth_header_value
                }
                async with client.stream("GET", x_file_location, headers=headers, follow_redirects=True) as response:
                    if response.status_code != 200:
                        raise HTTPException(status_code=400, detail=f"Failed to retrieve file, "
                                                                    f"response status: {response.status_code}")

                    content_length = response.headers.get("Content-Length")
                    if content_length and int(content_length) > MAX_FILE_SIZE_LIMIT_BYTES:
                        raise HTTPException(status_code=413, detail="File size exceeds maximum size limit")

                    # Validate that the response content is a valid JSON
                    try:
                        await response.aread()
                    except Exception as e:
                        raise HTTPException(status_code=400, detail=f"Unable to read data stream from "
                                                                    f"file location: {e!r}")

                    return response.content, response.encoding
    except Exception as e:
        if type(e) == HTTPException:
            raise e
        raise HTTPException(status_code=400, detail=f"Failed to retrieve file: {e!r}")


async def upload_file_contents(events: list[AbstractCalendarEvent], x_file_location: str, x_upload_http_method: str,
                               x_auth_header_name: Optional[str], x_auth_header_value: Optional[str],
                               x_data_encryption_password: Optional[str]):
    try:
        events_as_json_dict = jsonable_encoder(events)

        if x_data_encryption_password:
            content = encrypt(plaintext=json.dumps(events_as_json_dict),
                              password=x_data_encryption_password)
        else:
            content = json.dumps(events_as_json_dict).encode("utf-8")

        if x_file_location.startswith("https://github.com/"):
            try:
                github_client = GitHubClient(url=x_file_location, personal_access_token=x_auth_header_value)
            except ValueError as e:  # GitHub URL is malformed
                raise HTTPException(status_code=400, detail=f"Failed to upload file: {e}")

            try:
                github_client.check_data_and_pat_validity()
            except GithubException as e:
                raise HTTPException(status_code=400,
                                    detail=f"Failed to upload file: invalid GitHub PAT or owner/repo "
                                           f"was provided. Status {e.status} was returned, with "
                                           f"message '{e.message}'")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to upload file: unexpected error while checking "
                                                            f"GitHub data and PAT: {e!r}")

            try:
                github_client.upload_file(content)
            except GithubException as e:
                raise HTTPException(status_code=400, detail=f"Failed to upload file: {e.message}")
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Failed to upload file: unexpected error occurred while "
                                                            f"uploading file to GitHub: {e!r}")
        else:
            async with httpx.AsyncClient() as client:
                headers = dict()
                if x_auth_header_name and x_auth_header_value:
                    headers[x_auth_header_name] = x_auth_header_value

                response = await client.request(x_upload_http_method, url=x_file_location, headers=headers,
                                                content=content)

                if response.status_code < 200 or response.status_code > 204:
                    raise HTTPException(status_code=400, detail=f"Failed to upload file, "
                                                                f"response status: {response.status_code}")
    except Exception as e:
        if type(e) == HTTPException:
            raise e
        raise HTTPException(status_code=400, detail=f"Failed to upload file: {e!r}")
