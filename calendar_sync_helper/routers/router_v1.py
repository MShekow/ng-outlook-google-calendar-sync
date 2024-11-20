import json
from copy import copy
from typing import Annotated

import validators
from cryptography.exceptions import InvalidTag
from fastapi import Header, HTTPException, APIRouter

from calendar_sync_helper.cryptography_utils import decrypt
from calendar_sync_helper.entities.entities_v1 import CalendarEventList, OutlookCalendarEvent, AbstractCalendarEvent, \
    ComputeActionsInput, GoogleCalendarEvent, ComputeActionsResponse
from calendar_sync_helper.utils import is_syncblocker_event, separate_syncblocker_events, get_id_from_attendees, \
    build_syncblocker_attendees, get_syncblocker_title, fix_outlook_specific_field_defaults, get_boolean_header_value, \
    is_valid_sync_prefix, clean_id, filter_past_events, has_matching_title, download_file_contents, \
    upload_file_contents

router = APIRouter()


# Note: FastAPI behavior for headers that are set by the client, but contain no value (other than 0 or more spaces):
# FastAPI sets the header value to an empty string!


@router.get("/retrieve-calendar-file-proxy")
async def retrieve_calendar_file_proxy(
        x_file_location: Annotated[str | None, Header()] = None,
        x_auth_header_name: Annotated[str | None, Header()] = None,
        x_auth_header_value: Annotated[str | None, Header()] = None,
        x_data_encryption_password: Annotated[str | None, Header()] = None
):
    """
    Retrieves the real entries of a calendar stored in a file that is protected by an "Authorization" header, thus
    cannot be retrieved by the "Send an HTTP request to SharePoint" action directly.

    If x_data_encryption_password is set, the content at x_file_location is expected to be in binary form, and is
    decrypted using the x_data_encryption_password.
    """
    if not x_file_location or not x_auth_header_name or not x_auth_header_value:
        raise HTTPException(status_code=400, detail="Missing required headers")

    # Verify that the file location is a valid http(s) URL
    if not validators.url(x_file_location) or not x_file_location.startswith("http"):
        raise HTTPException(status_code=400, detail="Invalid file location, must be a valid http(s) URL")

    binary_data, encoding_hint = await download_file_contents(x_file_location, x_auth_header_name, x_auth_header_value)

    if x_data_encryption_password:
        try:
            file_as_text = decrypt(binary_data, password=x_data_encryption_password)
        except InvalidTag:
            raise HTTPException(status_code=400, detail="Unable to decrypt data, either wrong password "
                                                        "or data was manipulated")
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Unable to decrypt data, unexpected error "
                                                        f"occurred: {e!r}")
    else:
        try:
            file_as_text = binary_data.decode(encoding_hint or "utf-8")
        except UnicodeDecodeError:
            raise HTTPException(status_code=400, detail="Unable to decode binary response data to text")

    try:
        json_content = json.loads(file_as_text)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse JSON content: {e!r}")

    return json_content


@router.post("/extract-events")
async def extract_events(
        event_list: CalendarEventList,
        x_unique_sync_prefix: Annotated[str | None, Header()] = None,
        x_anonymize_fields: Annotated[str | None, Header()] = None,
        x_sync_events_without_attendees: Annotated[str | None, Header()] = None,
        x_relevant_response_types: Annotated[str | None, Header()] = None,
        x_file_location: Annotated[str | None, Header()] = None,
        x_upload_http_method: Annotated[str | None, Header()] = None,
        x_auth_header_name: Annotated[str | None, Header()] = None,
        x_auth_header_value: Annotated[str | None, Header()] = None,
        x_data_encryption_password: Annotated[str | None, Header()] = None
):
    """
    Returns a list of the real(!) events, normalizing the data structure of the events from different calendar
    providers. Blocker events are filtered out from the response.

    If x_anonymize_fields is set to a boolean value (e.g. to "1" or "yes"), the "sensitive" fields
    (specifically: title, location and description) are cleared, i.e., the values are set to empty strings in the
    response.

    If ignore_events_without_attendees is set to a boolean value, events that have no attendees are filtered out.

    If x_relevant_response_types is set (to a comma-separated list of values, e.g. "organizer,accepted"),
    and the events do contain a response type, events that have a NON-matching response type are filtered out.

    If x_file_location and x_upload_http_method are set, the returned response will also be uploaded to the provided
    location, using an (optional) header (x_auth_header_name, x_auth_header_value).

    If x_file_location is set and an x_data_encryption_password value is provided, the data is symmetrically encrypted
    with the x_data_encryption_password before uploading it to the x_file_location.
    """
    if not x_unique_sync_prefix:
        raise HTTPException(status_code=400, detail="You must provide the X-Unique-Sync-Prefix header")

    if not is_valid_sync_prefix(x_unique_sync_prefix):
        raise HTTPException(status_code=400, detail="Invalid X-Unique-Sync-Prefix value, must only contain "
                                                    "alphanumeric characters and dashes")

    anonymize_fields = get_boolean_header_value(x_anonymize_fields)
    sync_events_without_attendees = get_boolean_header_value(x_sync_events_without_attendees)

    relevant_response_types: list[str] = []
    if x_relevant_response_types:
        relevant_response_types = [item.strip() for item in x_relevant_response_types.split(",") if item]

    events = []
    for event in event_list.events:
        if isinstance(event, OutlookCalendarEvent):
            if relevant_response_types and event.responseType not in relevant_response_types:
                continue

        if is_syncblocker_event(event, unique_sync_prefix=x_unique_sync_prefix):
            continue

        if not sync_events_without_attendees:
            if isinstance(event, OutlookCalendarEvent) and not event.requiredAttendees:
                continue
            elif isinstance(event, GoogleCalendarEvent) and not event.attendees:
                continue

        e = AbstractCalendarEvent.from_implementation(event, anonymize_fields=anonymize_fields)
        events.append(e)

    if x_file_location:
        if not validators.url(x_file_location) or not x_file_location.startswith("http"):
            raise HTTPException(status_code=400, detail="Invalid file location, must be a valid http(s) URL")

        if not x_upload_http_method or x_upload_http_method.lower() not in ["put", "post"]:
            raise HTTPException(status_code=400, detail="Invalid upload method, must be PUT or POST")

        await upload_file_contents(events, x_file_location, x_upload_http_method, x_auth_header_name,
                                   x_auth_header_value, x_data_encryption_password)

    return events


@router.post("/compute-actions")
async def compute_actions(
        input_data: ComputeActionsInput,
        x_unique_sync_prefix: Annotated[str | None, Header()] = None,
        x_syncblocker_title_prefix: Annotated[str | None, Header()] = None,
        x_anonymized_title_placeholder: Annotated[str | None, Header()] = None,
        x_ignore_description_equality_check: Annotated[str | None, Header()] = None,
        x_disable_past_event_filter: Annotated[str | None, Header()] = None,
):
    """
    Figures out which cal1 SB events to delete, which ones to update, which ones to create, returning these actions as
    3 lists.

    Only events that start after <now> (server-time) are considered.
    """
    if not x_unique_sync_prefix:
        raise HTTPException(status_code=400, detail="You must provide the X-Unique-Sync-Prefix header")

    if not is_valid_sync_prefix(x_unique_sync_prefix):
        raise HTTPException(status_code=400, detail="Invalid X-Unique-Sync-Prefix value, must only contain "
                                                    "alphanumeric characters and dashes")

    # Strip leading and trailing double quotes, to allow for prefixes such as "Foo: " (FastAPI would otherwise
    # strip trailing spaces from header values, resulting in "Foo:")
    syncblocker_title_prefix = x_syncblocker_title_prefix
    if (x_syncblocker_title_prefix
            and x_syncblocker_title_prefix.startswith('"') and x_syncblocker_title_prefix.endswith('"')):
        syncblocker_title_prefix = x_syncblocker_title_prefix.lstrip('"').rstrip('"')

    ignore_description_equality_check = get_boolean_header_value(x_ignore_description_equality_check)
    disable_past_event_filter = get_boolean_header_value(x_disable_past_event_filter)

    events_to_delete: list[AbstractCalendarEvent] = []
    events_to_update: list[AbstractCalendarEvent] = []
    events_to_create: list[AbstractCalendarEvent] = []

    if not disable_past_event_filter:
        filter_past_events(input_data)

    cal1_real, cal1_syncblocker = separate_syncblocker_events(input_data.cal1events, x_unique_sync_prefix)
    cleaned_cal2_ids = {clean_id(event.sync_correlation_id) for event in input_data.cal2events}

    # Delete SyncBlocker events whose corresponding real events are no longer present
    for sync_blocker_event in cal1_syncblocker:
        if get_id_from_attendees(sync_blocker_event) not in cleaned_cal2_ids:
            events_to_delete.append(AbstractCalendarEvent.from_implementation(sync_blocker_event))

    # For each event e in cal2 where e.sync_correlation_id is not found in any cal1_syncblocker events, create an
    # event in cal1
    cal1_syncblocker_events_by_cleaned_id = {get_id_from_attendees(event): event for event in cal1_syncblocker}
    for event in input_data.cal2events:
        if clean_id(event.sync_correlation_id) not in cal1_syncblocker_events_by_cleaned_id:
            event_to_create = copy(event)
            event_to_create.attendees = build_syncblocker_attendees(x_unique_sync_prefix,
                                                                    real_event_correlation_id=event.sync_correlation_id)
            event_to_create.title = get_syncblocker_title(syncblocker_title_prefix, event.title,
                                                          x_anonymized_title_placeholder)
            event_to_create.sync_correlation_id = ""
            fix_outlook_specific_field_defaults(event_to_create)
            events_to_create.append(event_to_create)

    # For each event e in cal2 with a corresponding event in cal1_syncblocker events, but where the title, location,
    # description, start, end, is_all_day, show_as, sensitivity are different, update the event in cal1
    for event in input_data.cal2events:
        if clean_id(event.sync_correlation_id) in cal1_syncblocker_events_by_cleaned_id:
            cal1_syncblocker_event = cal1_syncblocker_events_by_cleaned_id[clean_id(event.sync_correlation_id)]
            abstract_cal1_sb_event = AbstractCalendarEvent.from_implementation(cal1_syncblocker_event)
            # In case cal2 contains Google events, make sure the comparison below works
            fix_outlook_specific_field_defaults(event)
            if (
                    not has_matching_title(abstract_cal1_sb_event.title, event.title, syncblocker_title_prefix,
                                           x_anonymized_title_placeholder) or
                    abstract_cal1_sb_event.location != event.location or
                    (not ignore_description_equality_check
                     and abstract_cal1_sb_event.description != event.description) or
                    abstract_cal1_sb_event.start != event.start or
                    abstract_cal1_sb_event.end != event.end or
                    abstract_cal1_sb_event.is_all_day != event.is_all_day or
                    (abstract_cal1_sb_event.show_as != event.show_as and abstract_cal1_sb_event.show_as is not None) or
                    (abstract_cal1_sb_event.sensitivity != event.sensitivity and
                     abstract_cal1_sb_event.sensitivity is not None)
            ):
                event_to_update = copy(event)
                # Note: update operations target the actual ID of the event, not the sync_correlation_id, but we simply
                # use that field as a placeholder for the ID here
                event_to_update.sync_correlation_id = abstract_cal1_sb_event.sync_correlation_id
                event_to_update.attendees = build_syncblocker_attendees(x_unique_sync_prefix,
                                                                        real_event_correlation_id=event.sync_correlation_id)
                event_to_update.title = get_syncblocker_title(syncblocker_title_prefix, event.title,
                                                              x_anonymized_title_placeholder)
                fix_outlook_specific_field_defaults(event_to_update)
                events_to_update.append(event_to_update)

    return ComputeActionsResponse(
        events_to_delete=events_to_delete,
        events_to_update=events_to_update,
        events_to_create=events_to_create
    )
