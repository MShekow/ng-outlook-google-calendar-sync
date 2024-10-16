import re
from datetime import datetime, date, time, UTC
from typing import Self, Optional

from pydantic import BaseModel


def clean_id(unclean_id: str) -> str:
    """ Remove any character that is not a-z, A-Z, or 0-9 """
    return re.sub(r'[^a-zA-Z0-9]', '', unclean_id)


class GoogleCalendarEvent(BaseModel):
    id: str  # may contain _ as illegal character
    # status: str  # only "confirmed" events are returned
    summary: str
    description: str
    location: str
    attendees: str  # separated by comma (or ", "), usually no comma if there is only 1 attendee
    start: datetime | date  # date for all-day events, otherwise Google uses e.g. 2024-01-05T19:15:00+00:00
    end: datetime | date


class OutlookCalendarEvent(BaseModel):
    id: str
    iCalUId: str
    subject: str
    body: str
    location: str
    startWithTimeZone: datetime  # 2017-08-29T04:00:00.0000000+00:00 or 2024-09-09T07:15:00+00:00
    endWithTimeZone: datetime
    requiredAttendees: str  # separated by semicolon, also if there is only 1 attendee (e.g. "foo@bar;")
    responseType: str
    isAllDay: bool
    showAs: str
    sensitivity: str


class AbstractCalendarEvent(BaseModel):
    sync_correlation_id: str
    title: str
    description: str
    location: str
    start: datetime
    end: datetime
    is_all_day: bool
    attendees: Optional[str] = None  # only filled by "compute-actions" endpoint, to insert the corresponding event's ID
    show_as: Optional[str] = None  # Outlook only
    sensitivity: Optional[str] = None  # Outlook only

    @classmethod
    def from_implementation(cls, event_impl: GoogleCalendarEvent | OutlookCalendarEvent,
                            anonymize_fields: bool = False) -> Self:
        if isinstance(event_impl, GoogleCalendarEvent):
            if type(event_impl.start) == date:
                # all-day event
                zero_am_utc = time(hour=0, minute=0, second=0, tzinfo=UTC)
                start_time = datetime.combine(event_impl.start, zero_am_utc)
                midnight_utc = time(hour=23, minute=59, second=59, tzinfo=UTC)
                end_time = datetime.combine(event_impl.end, midnight_utc)
                is_all_day = True
            else:
                start_time = event_impl.start
                end_time = event_impl.end
                is_all_day = False

            return cls(
                sync_correlation_id=clean_id(event_impl.id),
                title="" if anonymize_fields else event_impl.summary,
                description="" if anonymize_fields else event_impl.description,
                location="" if anonymize_fields else event_impl.location,
                start=start_time,
                end=end_time,
                is_all_day=is_all_day
            )

        return cls(
            sync_correlation_id=clean_id(event_impl.iCalUId),
            title="" if anonymize_fields else event_impl.subject,
            description="" if anonymize_fields else event_impl.body,
            location="" if anonymize_fields else event_impl.location,
            start=event_impl.startWithTimeZone,
            end=event_impl.endWithTimeZone,
            is_all_day=event_impl.isAllDay,
            show_as=event_impl.showAs,
            sensitivity=event_impl.sensitivity
        )

type ImplSpecificEvent = GoogleCalendarEvent | OutlookCalendarEvent

class CalendarEventList(BaseModel):
    events: list[ImplSpecificEvent]


class ComputeActionsInput(BaseModel):
    cal1events: list[ImplSpecificEvent]
    cal2events: list[AbstractCalendarEvent]
