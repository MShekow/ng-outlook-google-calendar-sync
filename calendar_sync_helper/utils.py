import re
from typing import Optional

from fastapi import HTTPException

from calendar_sync_helper.entities import ImplSpecificEvent, GoogleCalendarEvent, AbstractCalendarEvent


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

    # clean empty array slots and superfluous spaces
    attendees_cleaned = [attendee.strip() for attendee in attendees if bool(attendee)]

    if len(attendees_cleaned) != 1:
        return False

    attendee = attendees_cleaned[0]
    return attendee.endswith(".invalid") and attendee.startswith(f"{unique_sync_prefix}@")


def get_id_from_attendees(event: ImplSpecificEvent) -> str:
    """
    Assumes that the event is a SyncBlocker event. Returns the id stored in the attendee's email address.
    """
    attendees = extract_attendees(event)
    # attendees[0] has the form "<sync-prefix>@<id>.invalid"
    return attendees[0].split("@")[1].rstrip(".invalid")


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


def get_syncblocker_attendees(unique_sync_prefix: str, real_event_correlation_id: str) -> str:
    # TODO: need to handle ID-padding for the attendee email
    return f"{unique_sync_prefix}@{real_event_correlation_id}.invalid"


def get_syncblocker_title(syncblocker_prefix: Optional[str], event_title: str,
                          anonymized_title_placeholder: Optional[str]) -> str:
    title_placeholder = anonymized_title_placeholder if anonymized_title_placeholder else ""  # avoid "None" in title
    syncblocker_prefix = syncblocker_prefix if syncblocker_prefix else ""  # avoid "None" in title

    if not event_title:
        event_title = title_placeholder

    return syncblocker_prefix + event_title


def fix_outlook_specific_field_defaults(event: AbstractCalendarEvent):
    if event.show_as is None:
        event.show_as = "busy"

    if event.sensitivity is None:
        event.sensitivity = "normal"


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
