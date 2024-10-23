from datetime import datetime, date, time, UTC
from typing import Self, Optional

from pydantic import BaseModel


class GoogleCalendarEvent(BaseModel):
    id: str  # may contain _ as illegal character
    # status: str  # only "confirmed" events are returned
    summary: str
    description: str
    location: str
    attendees: str  # separated by comma (or ", "), usually no comma if there is only 1 attendee
    start: date | datetime  # date for all-day events, otherwise Google uses e.g. 2024-01-05T19:15:00+00:00
    end: date | datetime


class OutlookCalendarEvent(BaseModel):
    id: str
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
                # all-day event, where e.g. start="2024-10-01" and end="2024-10-02" indicates a ONE-day-long event,
                # that is, the interval notation would be: [start, end)

                # Convert the start/end date object to datetime objects
                zero_am_utc = time(hour=0, minute=0, second=0, tzinfo=UTC)
                start_time = datetime.combine(event_impl.start, zero_am_utc)
                if not type(event_impl.end) == date:
                    raise ValueError(f"For event titled '{event_impl.summary}', the start is a date (not datetime), "
                                     f"but the end is a datetime, which makes no sense")
                date_diff = event_impl.end - event_impl.start
                if date_diff.days == 0:
                    raise ValueError(f"For event titled '{event_impl.summary}', the start and end date is the same,"
                                     f"'{event_impl.start}', but expected it to be at least one day apart")

                end_time = datetime.combine(event_impl.end, zero_am_utc)
                is_all_day = True
            else:
                start_time = event_impl.start
                end_time = event_impl.end
                is_all_day = False

            return cls(
                sync_correlation_id=event_impl.id,
                title="" if anonymize_fields else event_impl.summary,
                description="" if anonymize_fields else event_impl.description,
                location="" if anonymize_fields else event_impl.location,
                start=start_time,
                end=end_time,
                is_all_day=is_all_day
            )

        return cls(
            sync_correlation_id=event_impl.id,
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


class ComputeActionsResponse(BaseModel):
    events_to_delete: list[AbstractCalendarEvent]
    events_to_update: list[AbstractCalendarEvent]
    events_to_create: list[AbstractCalendarEvent]
