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
    id_with_padding = attendees[0].split("@")[1].rstrip(".invalid")
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
    <unique-sync-prefix>@<padding>-<real-event-correlation-id>.invalid

    The reason why we add a padding is that some calendar providers (so far, only Outlook), may actually try to send
    event invitation emails when creating an event in the calendar (Googles does NOT). In case of Outlook, this would
    cause notification emails in your account, complaining that these invitation mails cannot be delivered (because of
    the ".invalid" domain). However, these event invitation mails only seem to be sent if the host is rather short.
    By adding a padding (making the DNS longer), the problem no longer occurs.
    """
    attendee_address_without_padding = f"{unique_sync_prefix}@{real_event_correlation_id}.invalid"
    number_of_padding_chars = 255 - len(attendee_address_without_padding)
    if number_of_padding_chars < 2:  # 2 because we want to add at least "a-"
        raise HTTPException(status_code=400, detail=f"Unique sync prefix is too long to build an attendee email."
                                                    f"For event with ID '{real_event_correlation_id}' "
                                                    f"(length:  {len(real_event_correlation_id)}) there are too few "
                                                    f"padding chars left: {number_of_padding_chars}. Please shorten "
                                                    f"your unique sync prefix")

    padding = "a" * (number_of_padding_chars - 1)
    return f"{unique_sync_prefix}@{padding}-{real_event_correlation_id}.invalid"


def get_syncblocker_title(syncblocker_title_prefix: Optional[str], event_title: str,
                          anonymized_title_placeholder: Optional[str]) -> str:
    title_placeholder = anonymized_title_placeholder if anonymized_title_placeholder else ""  # avoid "None" in title
    syncblocker_title_prefix = syncblocker_title_prefix if syncblocker_title_prefix else ""  # avoid "None" in title

    if not event_title:
        event_title = title_placeholder

    return syncblocker_title_prefix + event_title


def fix_outlook_specific_field_defaults(event: AbstractCalendarEvent):
    if event.show_as is None:
        event.show_as = "busy"

    if event.sensitivity is None:
        event.sensitivity = "normal"


def strip_syncblocker_title_prefix(event_title: str, syncblocker_title_prefix: Optional[str]) -> str:
    if not syncblocker_title_prefix:
        return event_title

    if event_title.startswith(syncblocker_title_prefix):
        return event_title[len(syncblocker_title_prefix):]


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
